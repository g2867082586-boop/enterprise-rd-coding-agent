const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

function csrfToken() {
  const item = document.cookie.split("; ").find(value => value.startsWith("nebula_csrf="));
  return item ? decodeURIComponent(item.split("=", 2)[1]) : "";
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const csrf = csrfToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(csrf && options.method && options.method !== "GET" ? { "X-CSRF-Token": csrf } : {}),
      ...(options.headers || {}),
    },
  });
  if (response.status === 401 && !path.includes("/auth/login") && !path.includes("/auth/register")) {
    window.dispatchEvent(new Event("auth-expired"));
  }
  if (!response.ok) {
    let message = "请求失败，请稍后重试";
    try {
      const data = await response.json();
      message = typeof data.detail === "string" ? data.detail : message;
    } catch { /* response intentionally sanitized */ }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function apiForm<T>(path: string, body: FormData): Promise<T> {
  const csrf = csrfToken();
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body,
    credentials: "include",
    headers: csrf ? { "X-CSRF-Token": csrf } : {},
  });
  if (!response.ok) {
    let message = "上传失败";
    try {
      const data = await response.json();
      message = typeof data.detail === "string" ? data.detail : message;
    } catch { /* response intentionally sanitized */ }
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}
