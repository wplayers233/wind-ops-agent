/// <reference types="vite/client" />

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') || 'http://127.0.0.1:8000';

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  const body = await response.text();
  if (!response.ok) {
    let message = body || `请求失败：HTTP ${response.status}`;
    try {
      const parsed = JSON.parse(body) as { detail?: unknown };
      if (parsed && typeof parsed.detail === 'string' && parsed.detail.trim()) message = parsed.detail;
    } catch {
      // 响应体不是 JSON（如网关错误页）时保留原始文本
    }
    throw new Error(message);
  }
  return (body ? JSON.parse(body) : {}) as T;
}
