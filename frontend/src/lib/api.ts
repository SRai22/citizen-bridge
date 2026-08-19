import type {
  ApprovalRequest,
  CitizenCase,
  ExternalApplication,
  TaskDetail,
} from "@/types/api";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...init.headers },
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new ApiError("The Citizen Bridge service is currently unreachable.");
  }

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const serverDetail = typeof payload?.detail === "string" ? payload.detail : null;
    const message =
      serverDetail ?? (response.status === 404
        ? "The requested record could not be found."
        : response.status === 503
          ? "The Citizen Bridge service is currently unreachable."
          : "The request failed.");
    throw new ApiError(
      message,
      response.status,
    );
  }
  return (await response.json()) as T;
}

export function getCase(caseId: string, signal?: AbortSignal): Promise<CitizenCase> {
  return request<CitizenCase>(`/api/cases/${encodeURIComponent(caseId)}`, { signal });
}

export function getTask(
  caseId: string,
  taskId: string,
  signal?: AbortSignal,
): Promise<TaskDetail> {
  return request<TaskDetail>(
    `/api/cases/${encodeURIComponent(caseId)}/tasks/${encodeURIComponent(taskId)}`,
    { signal },
  );
}

export function updateTaskInput(
  caseId: string,
  taskId: string,
  inputData: Record<string, unknown>,
): Promise<TaskDetail> {
  return request<TaskDetail>(
    `/api/cases/${encodeURIComponent(caseId)}/tasks/${encodeURIComponent(taskId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_data: inputData }),
    },
  );
}

export function prepareTask(
  caseId: string,
  taskId: string,
): Promise<ApprovalRequest | ExternalApplication> {
  return request<ApprovalRequest | ExternalApplication>(
    `/api/cases/${encodeURIComponent(caseId)}/tasks/${encodeURIComponent(taskId)}/prepare`,
    { method: "POST" },
  );
}

export function approveSubmission(approvalId: string): Promise<ExternalApplication> {
  return request<ExternalApplication>(
    `/api/approvals/${encodeURIComponent(approvalId)}/approve`,
    { method: "POST" },
  );
}

export function rejectSubmission(approvalId: string): Promise<ApprovalRequest> {
  return request<ApprovalRequest>(
    `/api/approvals/${encodeURIComponent(approvalId)}/reject`,
    { method: "POST" },
  );
}
