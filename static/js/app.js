// ===== Shared Utilities =====

// Escape a string for safe interpolation into innerHTML.
function escapeHtml(value) {
    return String(value == null ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

// URLs where a 401 is an expected outcome (bad credentials), NOT a session
// expiry, so the caller should render the error instead of being redirected.
const AUTH_ENDPOINTS = ["/api/login", "/api/register"];

function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
    return match ? decodeURIComponent(match[2]) : null;
}

async function apiFetch(url, options = {}) {
    const defaults = {
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
    };
    const config = { ...defaults, ...options, headers: { ...defaults.headers, ...options.headers } };

    // Echo the CSRF token back on state-changing requests (double-submit).
    const method = (config.method || "GET").toUpperCase();
    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
        const csrf = getCookie("csrf_token");
        if (csrf) config.headers["X-CSRF-Token"] = csrf;
    }

    let response;
    try {
        response = await fetch(url, config);
    } catch (err) {
        showToast("Network error. Please check your connection and try again.", "error");
        return { ok: false, status: 0, data: { error: "Network error" } };
    }

    // A session that expired mid-session should bounce to the landing page, but
    // a 401 from the login/register forms is a real error the form must display.
    const isAuthEndpoint = AUTH_ENDPOINTS.some(e => url.startsWith(e));
    if (response.status === 401 && !isAuthEndpoint) {
        window.location.href = "/";
        return null;
    }

    let data = null;
    try {
        data = await response.json();
    } catch (err) {
        data = { error: "Unexpected server response" };
    }

    return { ok: response.ok, status: response.status, data };
}

function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// Achievement icons are resolved server-side and delivered as `icon_emoji`
// (see models.ICON_EMOJI), so there is no icon map duplicated in the client.
const FALLBACK_ICON = "\u{1F3C5}";

// ===== Navbar Toggle =====
document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.querySelector(".nav-toggle");
    const links = document.querySelector(".nav-links");
    if (toggle && links) {
        toggle.addEventListener("click", () => links.classList.toggle("open"));
    }

    // Logout handler
    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", async () => {
            await apiFetch("/api/logout", { method: "POST" });
            window.location.href = "/";
        });
    }
});
