"""HashiCorp Vault integration helpers."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict

from .config import get_settings

try:  # pragma: no cover - optional dependency errors handled at runtime
    import hvac
except ImportError:  # pragma: no cover - handled gracefully when vault disabled
    hvac = None  # type: ignore

logger = logging.getLogger("app.vault")


def _is_configured(settings) -> bool:
    return bool(
        settings.vault_enabled
        and settings.vault_addr
        and settings.vault_token
        and settings.vault_mount_point
        and settings.vault_path_prefix
    )


def _build_client(settings):  # pragma: no cover - trivial wrapper
    if hvac is None:
        raise RuntimeError("hvac library is required for Vault integration")
    client = hvac.Client(
        url=settings.vault_addr,
        token=settings.vault_token,
        verify=settings.vault_verify_ssl,
    )
    if settings.vault_namespace:
        client.adapter.session.headers.update({"X-Vault-Namespace": settings.vault_namespace})
    return client


def _encode_for_transit(value: Any) -> str:
    raw = json.dumps(value)
    return base64.b64encode(raw.encode("utf-8")).decode("utf-8")


def _encrypt_metadata(client, settings, metadata: Dict[str, Any]) -> dict[str, str]:  # pragma: no cover - runtime
    encrypted: dict[str, str] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        kwargs = {
            "mount_point": settings.vault_mount_point,
            "name": settings.vault_transit_key,
            "plaintext": _encode_for_transit(value),
        }
        if settings.vault_transit_key_version:
            kwargs["key_version"] = settings.vault_transit_key_version
        response = client.secrets.transit.encrypt_data(**kwargs)
        ciphertext = response.get("data", {}).get("ciphertext")
        if not ciphertext:
            raise RuntimeError("Vault transit encryption failed to return ciphertext")
        encrypted[f"meta_{key}"] = ciphertext
    return encrypted


def store_api_key_secret(name: str, plaintext: str, metadata: dict[str, Any] | None = None) -> bool:
    """Persist the generated API key secret to Vault when configured."""

    settings = get_settings()
    if not _is_configured(settings):
        logger.debug("vault_not_configured")
        return False

    try:
        client = _build_client(settings)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("vault_client_initialisation_failed", extra={"error": str(exc)})
        return False

    secret_path = f"{settings.vault_path_prefix.rstrip('/')}/{name}"
    payload = {"api_key": plaintext}
    metadata = metadata or {}
    if metadata:
        if settings.vault_transit_key:
            try:
                payload.update(_encrypt_metadata(client, settings, metadata))
            except Exception as exc:  # pragma: no cover - depends on vault runtime
                logger.error(
                    "vault_transit_encryption_failed",
                    extra={"path": secret_path, "error": str(exc)},
                )
                # Fall back to plaintext metadata for resilience
                payload.update({f"meta_{key}": value for key, value in metadata.items() if value is not None})
        else:
            payload.update({f"meta_{key}": value for key, value in metadata.items() if value is not None})

    try:
        client.secrets.kv.v2.create_or_update_secret(
            mount_point=settings.vault_mount_point,
            path=secret_path,
            secret=payload,
        )
        logger.info("vault_secret_stored", extra={"path": secret_path})
        if settings.vault_verify_writes:
            stored = client.secrets.kv.v2.read_secret_version(
                mount_point=settings.vault_mount_point,
                path=secret_path,
            )
            remote_payload = stored.get("data", {}).get("data", {})
            if remote_payload.get("api_key") != plaintext:
                logger.error(
                    "vault_secret_verification_failed", extra={"path": secret_path}
                )
                return False
        return True
    except Exception as exc:  # pragma: no cover - network errors
        logger.error(
            "vault_secret_write_failed", extra={"path": secret_path, "error": str(exc)}
        )
        return False
