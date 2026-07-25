/**
 * Typed client for the backend API.
 *
 * The token lives in sessionStorage rather than localStorage: it should not
 * outlive the tab. No systeme.io key, and no secret of any kind, ever reaches
 * this layer — every outbound call to systeme.io happens server-side.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export type TaskStatus =
  | 'pending'
  | 'claimed'
  | 'working'
  | 'done'
  | 'error'
  | 'awaiting_approval'
  | 'blocked'
  | 'cancelled';

export interface Task {
  task_id: number;
  project_id: number;
  task_type: string;
  assigned_to: string;
  status: TaskStatus;
  input: Record<string, unknown>;
  output: Record<string, unknown> | null;
  depends_on: number[];
  attempts: number;
  error: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface Project {
  project_id: number;
  user_id: number;
  name: string;
  goal: string;
  niche: string | null;
  status: string;
  created_at: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.sessionStorage.getItem('aibo_token');
}

export function setToken(token: string): void {
  window.sessionStorage.setItem('aibo_token', token);
}

export function clearToken(): void {
  window.sessionStorage.removeItem('aibo_token');
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Non-JSON error body; the status text is all we have.
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  async login(email: string, password: string): Promise<string> {
    // The token endpoint takes form encoding, per the OAuth2 password flow.
    const body = new URLSearchParams({ username: email, password });
    const response = await fetch(`${API_BASE}/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
    if (!response.ok) throw new ApiError('Incorrect email or password', response.status);
    const data = await response.json();
    setToken(data.access_token);
    return data.access_token;
  },

  listProjects: () => request<Project[]>('/projects'),

  getProject: (id: number) => request<Project>(`/projects/${id}`),

  createProject: (payload: { name: string; goal: string; niche?: string }) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify(payload) }),

  projectTasks: (id: number) => request<Task[]>(`/projects/${id}/tasks`),

  pendingApproval: () => request<Task[]>('/tasks/pending-approval'),

  approveTask: (id: number) => request<Task>(`/tasks/${id}/approve`, { method: 'POST' }),

  rejectTask: (id: number, reason?: string) =>
    request<Task>(
      `/tasks/${id}/reject${reason ? `?reason=${encodeURIComponent(reason)}` : ''}`,
      { method: 'POST' },
    ),
};
