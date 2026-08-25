import type {
  ApprovalRequest,
  AuthSession,
  CaseOverview,
  CatalogService,
  CitizenCase,
  DocumentRequirement,
  ExternalApplication,
  IntakeConfirmation,
  IntakeHouseholdProfile,
  IntakeResponse,
  LifeEventCategory,
  RejectionInterpretation,
  RemediationAction,
  TaskDetail,
} from "@/types/api";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface RegistrationInput {
  username: string;
  password: string;
  name?: string;
  date_of_birth?: string;
  city?: string;
  state?: string;
  phone?: string;
}

export function register(input: RegistrationInput): Promise<{ user_id: string }> {
  return request("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function login(username: string, password: string): Promise<{ user_id: string }> {
  return request("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
}

export function getSession(signal?: AbortSignal): Promise<AuthSession> {
  return request<AuthSession>("/api/auth/session", { signal });
}

export function updateProfile(input: {
  name?: string;
  date_of_birth?: string;
  city?: string;
  state?: string;
  phone?: string;
}): Promise<AuthSession> {
  return request<AuthSession>("/api/auth/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function getCategories(): Promise<{ categories: LifeEventCategory[] }> {
  return request("/api/catalog/categories");
}

export function startIntake(categoryId: string, signal?: AbortSignal): Promise<IntakeResponse> {
  return request<IntakeResponse>("/api/intake/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category_id: categoryId }),
    signal,
  });
}

export function sendIntakeMessage(
  sessionId: string,
  message: string,
): Promise<IntakeResponse> {
  return request<IntakeResponse>(`/api/intake/${encodeURIComponent(sessionId)}/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
}

export async function confirmIntake(
  sessionId: string,
  categoryId: string,
): Promise<IntakeConfirmation> {
  const { profile } = await request<{ profile: IntakeHouseholdProfile }>(
    `/api/intake/${encodeURIComponent(sessionId)}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_confirmed: true }),
  });
  const bereavement = categoryId === "bereavement";
  return request<IntakeConfirmation>("/api/cases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      life_event: {
        type: categoryId,
        context: {
          category_id: categoryId,
          ...(bereavement
            ? {
                deceased: {
                  is_deceased: true,
                  pension_status: profile.deceased.pension_status,
                  was_electricity_account_holder: profile.assets.bescom,
                  was_head_of_household: true,
                },
                surviving_spouse: { exists: profile.surviving_members.length > 0 },
                location: { state: profile.location.state },
                assets: profile.assets,
              }
            : {}),
        },
      },
      household_profile: {
        location_city: profile.location.city,
        location_state: profile.location.state,
        people: [
          {
            name: profile.deceased.name,
            relationship: profile.deceased.relationship,
            role: null,
            is_deceased: bereavement,
            attributes: {
              occupation: profile.deceased.occupation,
              pension_status: profile.deceased.pension_status,
            },
          },
          ...profile.surviving_members.map((person) => ({
            name: person.name,
            relationship: person.relationship,
            role: null,
            is_deceased: false,
            attributes: {
              occupation: person.occupation,
              pension_status: person.pension_status,
            },
          })),
        ],
      },
      ...(bereavement ? { subject_person_index: 0, subject_relationship: profile.deceased.relationship } : {}),
    }),
  });
}

export function getCatalogServices(): Promise<{ services: CatalogService[] }> {
  return request("/api/catalog/services");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: { Accept: "application/json", ...init.headers },
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new ApiError("The Citizen Bridge service is currently unreachable.");
  }

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = payload?.detail;
    const serverDetail =
      typeof detail === "string"
        ? detail
        : detail &&
            typeof detail === "object" &&
            "message" in detail &&
            typeof detail.message === "string"
          ? detail.message
          : null;
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

export function getCaseOverview(caseId: string, signal?: AbortSignal): Promise<CaseOverview> {
  return request<CaseOverview>(`/api/cases/${encodeURIComponent(caseId)}`, { signal });
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

export function getTaskRequirements(
  caseId: string,
  taskId: string,
  signal?: AbortSignal,
): Promise<DocumentRequirement[]> {
  return request<DocumentRequirement[]>(
    `/api/cases/${encodeURIComponent(caseId)}/tasks/${encodeURIComponent(taskId)}/requirements`,
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

export function interpretRejection(
  caseId: string,
  taskId: string,
  signal?: AbortSignal,
): Promise<RejectionInterpretation> {
  return request<RejectionInterpretation>(
    `/api/cases/${encodeURIComponent(caseId)}/tasks/${encodeURIComponent(taskId)}/interpret-rejection`,
    { method: "POST", signal },
  );
}

export function acceptRemediation(
  caseId: string,
  remediation: RemediationAction,
): Promise<CitizenCase> {
  return request<CitizenCase>(
    `/api/cases/${encodeURIComponent(caseId)}/accept-remediation`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(remediation),
    },
  );
}

export interface SeedResponse {
  case_id: string;
  state: string;
  tasks: number;
}

export function resetDemo(): Promise<{ status: string }> {
  return request<{ status: string }>("/api/demo/reset", { method: "POST" });
}

export function seedDemo(
  state: "initial" | "after_death_cert" | "after_bescom_rejection" = "initial",
): Promise<SeedResponse> {
  return request<SeedResponse>(`/api/demo/seed?state=${state}`, { method: "POST" });
}
