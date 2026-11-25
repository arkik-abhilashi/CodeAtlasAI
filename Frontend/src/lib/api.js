const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const TOKEN_KEY = "codeatlas.accessToken";

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function saveSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem("codeatlas.user", JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem("codeatlas.user");
}

export function getCachedUser() {
  try { return JSON.parse(localStorage.getItem("codeatlas.user") || "null"); }
  catch { return null; }
}

export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let body = options.body;
  if (body && !(body instanceof FormData) && typeof body !== "string") {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(body);
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers, body });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && token) window.dispatchEvent(new CustomEvent("codeatlas:unauthorized"));
    throw new Error(data.detail || data.message || `Request failed (${response.status})`);
  }
  return data;
}
