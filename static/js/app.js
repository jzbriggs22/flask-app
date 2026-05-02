// ===== Shared Utilities =====

async function apiFetch(url, options = {}) {
    const defaults = {
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
    };
    const config = { ...defaults, ...options, headers: { ...defaults.headers, ...options.headers } };

    const response = await fetch(url, config);
    const data = await response.json();

    if (response.status === 401) {
        window.location.href = "/";
        return null;
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

const ICON_MAP = {
    egg: "\u{1F95A}", eyes: "\u{1F440}", binoculars: "\u{1F52D}", star: "\u{2B50}",
    crown: "\u{1F451}", seedling: "\u{1F331}", herb: "\u{1F33F}", book: "\u{1F4D6}",
    mortar_board: "\u{1F393}", fire: "\u{1F525}", mag: "\u{1F50D}", gem: "\u{1F48E}",
    dizzy: "\u{1F4AB}", trophy: "\u{1F3C6}", bird: "\u{1F426}", eagle: "\u{1F985}",
    rocket: "\u{1F680}", "100": "\u{1F4AF}",
};

function getEmoji(iconName) {
    return ICON_MAP[iconName] || "\u{1F3C5}";
}

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
