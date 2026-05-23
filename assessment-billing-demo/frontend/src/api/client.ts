export interface Assessment {
  id: number;
  title: string;
  subject_name: string;
  score: number;
  status: "draft" | "submitted" | "reviewed";
  notes: string | null;
  created_at: string;
}

export interface AssessmentCreate {
  title: string;
  subject_name: string;
  score: number;
  status: "draft" | "submitted" | "reviewed";
  notes?: string;
}

export interface BillingStatus {
  plan: string;
  status: string;
  assessments_used: number;
  assessments_limit: number;
  remaining: number;
  updated_at: string;
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof detail.detail === "string" ? detail.detail : "Request failed");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  listAssessments: () => request<Assessment[]>("/api/assessments"),
  createAssessment: (payload: AssessmentCreate) =>
    request<Assessment>("/api/assessments", { method: "POST", body: JSON.stringify(payload) }),
  deleteAssessment: (id: number) =>
    request<void>(`/api/assessments/${id}`, { method: "DELETE" }),
  getBillingStatus: () => request<BillingStatus>("/api/billing/status"),
};
