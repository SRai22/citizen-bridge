import type { CitizenCase, TaskDetail } from "@/types/api";

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

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: "application/json" },
      signal,
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new ApiError("The Citizen Bridge service is currently unreachable.");
  }

  if (!response.ok) {
    const message =
      response.status === 404
        ? "The requested record could not be found."
        : response.status === 503
          ? "The Citizen Bridge service is currently unreachable."
          : "The request failed.";
    throw new ApiError(
      message,
      response.status,
    );
  }
  return (await response.json()) as T;
}

export function getCase(caseId: string, signal?: AbortSignal): Promise<CitizenCase> {
  return request<CitizenCase>(`/api/cases/${encodeURIComponent(caseId)}`, signal);
}

export function getTask(
  caseId: string,
  taskId: string,
  signal?: AbortSignal,
): Promise<TaskDetail> {
  return request<TaskDetail>(
    `/api/cases/${encodeURIComponent(caseId)}/tasks/${encodeURIComponent(taskId)}`,
    signal,
  );
}
