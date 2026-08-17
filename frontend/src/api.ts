import { AIConfig, AITask, AITaskResult, AuthSession, AuthUser, ExportMode, Project, PromptTemplate, ProviderPreset, ReviewStatus, Sample, Stats } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";
const AUTH_TOKEN_STORAGE_KEY = "qa-review-auth-token";

let authToken = window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) || "";

export function setAuthToken(token: string) {
  authToken = token;
  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
}

export function clearAuthToken() {
  authToken = "";
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
}

function authHeaders(headers?: HeadersInit): HeadersInit {
  return authToken ? { Authorization: `Bearer ${authToken}`, ...(headers ?? {}) } : (headers ?? {});
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: authHeaders({ "Content-Type": "application/json", ...(init?.headers ?? {}) })
    });
  } catch (err) {
    throw new Error(`无法连接后端服务：${API_BASE}`);
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(readApiError(detail) || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function formRequest<T>(path: string, body: FormData): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      body,
      headers: authHeaders()
    });
  } catch (err) {
    throw new Error(`无法连接后端服务：${API_BASE}`);
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(readApiError(detail) || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function blobRequest(path: string, init?: RequestInit): Promise<{ blob: Blob; filename: string }> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers: authHeaders(init?.headers) });
  } catch (err) {
    throw new Error(`无法连接后端服务：${API_BASE}`);
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(readApiError(detail) || `HTTP ${response.status}`);
  }
  return { blob: await response.blob(), filename: readFilename(response.headers.get("content-disposition")) };
}

function readApiError(detail: string) {
  try {
    const parsed = JSON.parse(detail);
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail)) return parsed.detail.map((item: { msg?: string }) => item.msg || JSON.stringify(item)).join("\n");
  } catch {
    return detail;
  }
  return detail;
}

function readFilename(disposition: string | null) {
  const fallback = `export-${Date.now()}.jsonl`;
  if (!disposition) return fallback;
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1]);
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return match?.[1] || fallback;
}

export const api = {
  projects: () => request<Project[]>("/projects"),
  requestCode: (email: string) => request<{ ok: boolean; expires_in_minutes: number; debug_code?: string | null }>("/auth/request-code", { method: "POST", body: JSON.stringify({ email }) }),
  verifyCode: (email: string, code: string) => request<AuthSession>("/auth/verify-code", { method: "POST", body: JSON.stringify({ email, code }) }),
  me: () => request<AuthUser>("/auth/me"),
  createProject: (payload: { name: string; dataset_type: string; source_path: string; project_path: string; media_path?: string }) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(payload) }),
  deleteProject: (projectId: string) => request<{ ok: boolean }>(`/projects/${projectId}`, { method: "DELETE" }),
  createProjectUpload: (payload: { name: string; dataset_type: string; project_path?: string; datasetFile: File; mediaFiles: File[] }) => {
    const body = new FormData();
    body.append("name", payload.name);
    body.append("dataset_type", payload.dataset_type);
    if (payload.project_path) body.append("project_path", payload.project_path);
    body.append("dataset_file", payload.datasetFile, payload.datasetFile.name);
    payload.mediaFiles.forEach((file) => body.append("media_files", file, (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name));
    return formRequest<Project>("/projects/upload", body);
  },
  inspect: (path: string) => request(`/projects/inspect?path=${encodeURIComponent(path)}`, { method: "POST" }),
  inspectUpload: (file: File) => {
    const body = new FormData();
    body.append("dataset_file", file, file.name);
    return formRequest("/projects/inspect-upload", body);
  },
  mediaUrl: (projectId: string, path: string) => `${API_BASE}/projects/${projectId}/media?path=${encodeURIComponent(path)}`,
  mediaBlob: (projectId: string, path: string) => blobRequest(`/projects/${projectId}/media?path=${encodeURIComponent(path)}`),
  samples: (projectId: string, status = "ALL", q = "", limit = 50, offset = 0) =>
    request<{ items: Sample[]; total: number; limit: number; offset: number }>(
      `/projects/${projectId}/samples?status=${encodeURIComponent(status)}&q=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}`
    ),
  review: (projectId: string, sampleId: number, payload: { status: ReviewStatus; note?: string }) =>
    request<Sample>(`/projects/${projectId}/samples/${sampleId}/review`, { method: "POST", body: JSON.stringify(payload) }),
  undo: (projectId: string) => request<{ ok: boolean }>(`/projects/${projectId}/samples/undo`, { method: "POST" }),
  providers: () => request<ProviderPreset[]>("/providers"),
  localProxy: () => request<{ proxy_url: string }>("/providers/local-proxy"),
  configs: (projectId: string) => request<AIConfig[]>(`/projects/${projectId}/ai/configs`),
  saveConfig: (projectId: string, payload: AIConfig) => request<AIConfig>(`/projects/${projectId}/ai/configs`, { method: "POST", body: JSON.stringify(payload) }),
  testConfig: (projectId: string, payload: AIConfig) => request(`/projects/${projectId}/ai/test`, { method: "POST", body: JSON.stringify(payload) }),
  chatTest: (projectId: string, payload: AIConfig & { prompt: string }) =>
    request<{ ok: boolean; content: string; elapsed_ms: number; protocol: string; model: string }>(`/projects/${projectId}/ai/chat-test`, { method: "POST", body: JSON.stringify(payload) }),
  prompts: (projectId: string) => request<PromptTemplate[]>(`/projects/${projectId}/prompts`),
  savePrompt: (projectId: string, payload: { name: string; content: string }) =>
    request<PromptTemplate>(`/projects/${projectId}/prompts`, { method: "POST", body: JSON.stringify(payload) }),
  updatePrompt: (projectId: string, promptId: number, payload: { name: string; content: string }) =>
    request<PromptTemplate>(`/projects/${projectId}/prompts/${promptId}`, { method: "PUT", body: JSON.stringify(payload) }),
  startTask: (projectId: string, payload: { config_id: number; prompt_id: number; range_filter: string }) =>
    request<AITask>(`/projects/${projectId}/ai/tasks`, { method: "POST", body: JSON.stringify(payload) }),
  tasks: (projectId: string) => request<AITask[]>(`/projects/${projectId}/ai/tasks`),
  taskResults: (projectId: string, taskId: number, limit = 80) => request<AITaskResult[]>(`/projects/${projectId}/ai/tasks/${taskId}/results?limit=${limit}`),
  taskAction: (projectId: string, taskId: number, action: "pause" | "resume" | "stop" | "refresh") =>
    request<AITask>(`/projects/${projectId}/ai/tasks/${taskId}/${action}`, { method: "POST" }),
  stats: (projectId: string) => request<Stats>(`/projects/${projectId}/statistics`),
  exportProject: (projectId: string, mode: ExportMode) => blobRequest(`/projects/${projectId}/export/download?mode=${encodeURIComponent(mode)}`)
};
