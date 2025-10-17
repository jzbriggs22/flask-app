"""Command-line utilities for managing the Task Registry service."""

from __future__ import annotations

from datetime import datetime, timedelta
import secrets
from typing import List

import typer
from sqlalchemy import select

from .audit import audit_event
from .database import get_session_factory, init_engine
from .models import ApiKey, ApiKeyArchive
from .security import hash_api_key
from .vault import store_api_key_secret

app = typer.Typer(help="Manage API keys and operational tasks.")


@app.command("create-api-key")
def create_api_key(
    name: str = typer.Argument(..., help="Human-friendly key label."),
    owner_email: str = typer.Option("", help="Owner email for audit trails."),
    description: str = typer.Option("", help="Purpose of the API key."),
    scopes: List[str] = typer.Option(
        ["read", "write", "monitor"],
        help="Scopes granted to the API key (e.g. read,write,monitor).",
    ),
    ttl_days: int = typer.Option(
        0,
        help="Optional TTL in days before the key automatically expires (0 disables).",
        min=0,
    ),
) -> None:
    """Create a new API key and print the plaintext value once."""

    init_engine()
    SessionLocal = get_session_factory()

    with SessionLocal() as session:
        existing = session.execute(select(ApiKey).where(ApiKey.name == name)).scalar_one_or_none()
        if existing:
            typer.echo(f"An API key named '{name}' already exists.", err=True)
            raise typer.Exit(code=1)

        raw_key = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=ttl_days) if ttl_days else None
        record = ApiKey(
            name=name,
            owner_email=owner_email or None,
            description=description or None,
            key_hash=hash_api_key(raw_key),
            scopes=[scope.lower() for scope in scopes],
            expires_at=expires_at,
            last_rotated_at=datetime.utcnow(),
        )
        session.add(record)
        session.commit()

    metadata = {
        "owner_email": owner_email or None,
        "description": description or None,
        "scopes": ",".join(scopes),
        "expires_at": expires_at.isoformat() if expires_at else None,
    }
    vault_written = store_api_key_secret(name, raw_key, metadata)
    audit_event(
        "api_key_created",
        api_key_name=name,
        owner_email=owner_email or None,
        scopes=scopes,
        expires_at=metadata["expires_at"],
        vault_written=vault_written,
    )

    typer.echo(f"API key created for '{name}'.")
    typer.echo("Store this secret securely; it will not be shown again:")
    typer.echo(raw_key)
    if vault_written:
        typer.echo("Secret also stored in Vault.")


@app.command("list-api-keys")
def list_api_keys() -> None:
    """List existing API keys without revealing secrets."""

    init_engine()
    SessionLocal = get_session_factory()

    with SessionLocal() as session:
        records = session.execute(select(ApiKey).order_by(ApiKey.created_at.asc())).scalars().all()

    if not records:
        typer.echo("No API keys provisioned yet.")
        return

    for record in records:
        status = "active" if record.is_active else "inactive"
        typer.echo(
            f"[{record.id}] {record.name} - {status} | owner={record.owner_email or '-'} | scopes={','.join(record.scopes)} | "
            f"expires={record.expires_at or 'never'} | requests={record.request_count} | errors={record.error_count}"
        )


@app.command("deactivate-api-key")
def deactivate_api_key(name: str = typer.Argument(..., help="Name of the API key to disable.")) -> None:
    """Deactivate an API key by name."""

    init_engine()
    SessionLocal = get_session_factory()

    with SessionLocal() as session:
        record = session.execute(select(ApiKey).where(ApiKey.name == name)).scalar_one_or_none()
        if not record:
            typer.echo(f"No API key found for '{name}'.", err=True)
            raise typer.Exit(code=1)

        if not record.is_active:
            typer.echo(f"API key '{name}' is already inactive.")
            return

        record.is_active = False
        session.add(record)
        session.commit()

    audit_event("api_key_deactivated", api_key_name=name, owner_email=record.owner_email)
    typer.echo(f"API key '{name}' deactivated.")


@app.command("rotate-api-key")
def rotate_api_key(
    name: str = typer.Argument(..., help="Name of the API key to rotate."),
    ttl_days: int = typer.Option(
        0,
        help="Optional TTL in days for the new key before expiration (0 keeps existing expiry).",
        min=0,
    ),
) -> None:
    """Rotate an existing API key, returning a new secret and invalidating the old hash."""

    init_engine()
    SessionLocal = get_session_factory()

    with SessionLocal() as session:
        record = session.execute(select(ApiKey).where(ApiKey.name == name)).scalar_one_or_none()
        if not record:
            typer.echo(f"No API key found for '{name}'.", err=True)
            raise typer.Exit(code=1)

        raw_key = secrets.token_urlsafe(32)
        record.key_hash = hash_api_key(raw_key)
        record.is_active = True
        record.last_rotated_at = datetime.utcnow()
        if ttl_days:
            record.expires_at = datetime.utcnow() + timedelta(days=ttl_days)
        session.add(record)
        session.commit()
        metadata = {
            "owner_email": record.owner_email,
            "description": record.description,
            "scopes": ",".join(record.scopes or []),
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        }

    vault_written = store_api_key_secret(name, raw_key, metadata)
    audit_event(
        "api_key_rotated",
        api_key_name=name,
        owner_email=metadata["owner_email"],
        scopes=record.scopes,
        expires_at=metadata["expires_at"],
        vault_written=vault_written,
    )

    typer.echo(
        f"API key '{name}' rotated successfully. Distribute the new secret and revoke the old access promptly."
    )
    typer.echo(raw_key)
    if vault_written:
        typer.echo("Secret also stored in Vault.")


@app.command("bulk-set-scopes")
def bulk_set_scopes(
    names: List[str] = typer.Argument(..., help="API key names to update."),
    add: List[str] = typer.Option([], "--add", help="Scopes to add."),
    remove: List[str] = typer.Option([], "--remove", help="Scopes to remove."),
    replace: List[str] = typer.Option([], "--replace", help="Replace scopes entirely."),
) -> None:
    """Bulk adjust scopes across multiple API keys."""

    if not any([add, remove, replace]):
        typer.echo("Provide --add, --remove, or --replace scopes.", err=True)
        raise typer.Exit(code=1)

    init_engine()
    SessionLocal = get_session_factory()

    updated = []
    with SessionLocal() as session:
        for name in names:
            record = session.execute(select(ApiKey).where(ApiKey.name == name)).scalar_one_or_none()
            if not record:
                typer.echo(f"Skipping unknown API key '{name}'.", err=True)
                continue
            scopes = set(scope.lower() for scope in (record.scopes or []))
            if replace:
                scopes = {scope.lower() for scope in replace}
            else:
                scopes.update(scope.lower() for scope in add)
                scopes.difference_update(scope.lower() for scope in remove)
            record.scopes = sorted(scopes)
            session.add(record)
            updated.append((name, record.scopes))
        session.commit()

    for name, scopes in updated:
        typer.echo(f"Updated scopes for '{name}': {','.join(scopes)}")
        audit_event("api_key_scopes_updated", api_key_name=name, scopes=scopes)


@app.command("reassign-api-key-owner")
def reassign_api_key_owner(
    names: List[str] = typer.Argument(..., help="API key names to reassign."),
    owner_email: str = typer.Option(..., help="New owner email."),
    description: str = typer.Option("", help="Optional description to store."),
) -> None:
    """Reassign one or more API keys to a new owner."""

    init_engine()
    SessionLocal = get_session_factory()

    reassigned = []
    with SessionLocal() as session:
        for name in names:
            record = session.execute(select(ApiKey).where(ApiKey.name == name)).scalar_one_or_none()
            if not record:
                typer.echo(f"Skipping unknown API key '{name}'.", err=True)
                continue
            record.owner_email = owner_email
            if description:
                record.description = description
            session.add(record)
            reassigned.append(name)
        session.commit()

    for name in reassigned:
        typer.echo(f"Reassigned '{name}' to {owner_email}.")
        audit_event("api_key_owner_reassigned", api_key_name=name, owner_email=owner_email)


@app.command("describe-api-key")
def describe_api_key(name: str = typer.Argument(..., help="Name of the API key.")) -> None:
    """Print analytics and archive history for a specific API key."""

    init_engine()
    SessionLocal = get_session_factory()

    with SessionLocal() as session:
        record = session.execute(select(ApiKey).where(ApiKey.name == name)).scalar_one_or_none()
        if not record:
            typer.echo(f"No API key found for '{name}'.", err=True)
            raise typer.Exit(code=1)

        typer.echo(f"Name: {record.name}")
        typer.echo(f"Owner: {record.owner_email or '-'}")
        typer.echo(f"Description: {record.description or '-'}")
        typer.echo(f"Scopes: {','.join(record.scopes or [])}")
        typer.echo(f"Status: {'active' if record.is_active else 'inactive'}")
        typer.echo(f"Created: {record.created_at.isoformat()}")
        typer.echo(f"Last used: {record.last_used_at.isoformat() if record.last_used_at else '-'}")
        typer.echo(f"Expires: {record.expires_at.isoformat() if record.expires_at else 'never'}")
        typer.echo(f"Requests: {record.request_count}")
        typer.echo(f"Errors: {record.error_count}")
        if record.last_error_reason:
            typer.echo(
                f"Last error: {record.last_error_reason} at "
                f"{record.last_error_at.isoformat() if record.last_error_at else '-'}"
            )

        archives = (
            session.execute(
                select(ApiKeyArchive)
                .where(ApiKeyArchive.name == name)
                .order_by(ApiKeyArchive.archived_at.desc())
            )
            .scalars()
            .all()
        )

        if archives:
            typer.echo("Archive history:")
            for archive in archives:
                typer.echo(
                    f"  - {archive.archived_at.isoformat()} reason={archive.archive_reason or '-'} "
                    f"requests={archive.request_count} errors={archive.error_count}"
                )
        else:
            typer.echo("Archive history: none")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
