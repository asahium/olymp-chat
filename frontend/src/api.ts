// Thin API client. The browser sends ONLY conversation messages; it never
// knows about the model, token limits, or the provider key.

const TOKEN_KEY = "aioi_token";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface Me {
  participant_id: string;
  display_name: string;
  team_id: string | null;
  remaining_requests: number;
}

export interface ChatResult {
  message: { role: string; content: string };
  usage: {
    prompt_tokens: number | null;
    completion_tokens: number | null;
    total_tokens: number | null;
  };
  limits: { max_output_tokens: number };
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const resp = await fetch(path, { ...options, headers });
  if (resp.status === 401) {
    clearToken();
  }
  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`;
    try {
      const body = await resp.json();
      detail = body.detail || body.error || detail;
    } catch {
      /* keep default */
    }
    throw new ApiError(resp.status, detail);
  }
  return (await resp.json()) as T;
}

export async function login(loginCode: string): Promise<{ token: string; display_name: string }> {
  const data = await request<{ token: string; display_name: string }>("/api/login", {
    method: "POST",
    body: JSON.stringify({ login_code: loginCode }),
  });
  setToken(data.token);
  return data;
}

export async function me(): Promise<Me> {
  return request<Me>("/api/me");
}

export async function chat(messages: ChatMessage[]): Promise<ChatResult> {
  return request<ChatResult>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ messages }),
  });
}

export { ApiError };
