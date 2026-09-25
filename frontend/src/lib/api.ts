import axios from "axios";

export const SERVER_ORIGIN = "http://127.0.0.1:8000";
export const api = axios.create({ baseURL: `${SERVER_ORIGIN}/api` });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function apiErrorMessage(err: any): string {
  const detail = err?.response?.data?.detail;
  if (!detail) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (detail.message) {
    const reasons = detail.reasons ? `: ${detail.reasons.join(", ")}` : "";
    return `${detail.message}${reasons}`;
  }
  if (Array.isArray(detail)) return detail.map((d: any) => d.msg).join("; ");
  return JSON.stringify(detail);
}

/**
 * Plain <a href="...api..."> tags can't send the JWT Bearer token, so any
 * protected file download (PDF/Excel reports) needs to go through axios
 * (which attaches Authorization via the interceptor above), fetch the file
 * as a blob, then trigger the browser's save dialog manually.
 */
export async function downloadAuthenticated(path: string, filename: string) {
  const res = await api.get(path, { responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([res.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
