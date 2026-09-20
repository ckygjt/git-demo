import type { HealthInfo, RiskReport } from "@/types";

export const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) || "http://localhost:8000";

function readError(res: Response): Promise<never> {
  return res
    .text()
    .then((body) => Promise.reject(new Error(`后端返回 ${res.status}：${body || res.statusText}`)));
}

/** 图文联合检测（演示主接口） */
export function detectFull(file: File | null, text: string): Promise<RiskReport> {
  const form = new FormData();
  if (file) form.append("file", file);
  form.append("text", text);

  return fetch(`${API_BASE}/api/detect/full`, { method: "POST", body: form }).then((res) =>
    res.ok ? (res.json() as Promise<RiskReport>) : readError(res)
  );
}

/** 后端健康状态：用于展示 LLM 是否可用 */
export function fetchHealth(): Promise<HealthInfo> {
  return fetch(`${API_BASE}/api/health`).then((res) =>
    res.ok ? (res.json() as Promise<HealthInfo>) : readError(res)
  );
}
