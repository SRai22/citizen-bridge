import type {
  AccessLogEntry,
  ActivityFeedResponse,
  ActiveBenefit,
  ApprovalRequest,
  BenefitOpportunity,
  AuthSession,
  CaseOverview,
  CaseListItem,
  CatalogService,
  CitizenCase,
  DigestResponse,
  DeletionStatus,
  DocCategory,
  DocDetailEntry,
  DocEntry,
  DocumentShare,
  DocumentRequirement,
  ExternalApplication,
  FamilyMember,
  IntakeConfirmation,
  IntakeProfile,
  IntakeResponse,
  LifeEventCategory,
  NotificationItem,
  RejectionInterpretation,
  RemediationAction,
  TaskDetail,
  WithdrawableApplication,
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

export function requestPhoneOtp(phone: string, intent: "login" | "register"): Promise<{ sent: boolean; demo_code: string | null }> {
  return request("/api/auth/phone/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, intent }),
  });
}

export function verifyPhoneOtp(phone: string, code: string, intent: "login" | "register"): Promise<{ user_id: string; is_new_user: boolean }> {
  return request("/api/auth/phone/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, code, intent }),
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

export function logout(): Promise<void> {
  return request<void>("/api/auth/logout", { method: "POST" });
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
  subject: "self" | FamilyMember | null = null,
): Promise<IntakeConfirmation> {
  const { profile } = await request<{ profile: IntakeProfile }>(
    `/api/intake/${encodeURIComponent(sessionId)}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_confirmed: true }),
  });
  const profileMatchesCategory =
    (categoryId === "bereavement" && "deceased" in profile)
    || (categoryId === "new_baby" && "baby" in profile)
    || (categoryId === "marriage" && "spouse1" in profile);
  if (!profileMatchesCategory) {
    throw new ApiError(`Intake profile does not match category: ${categoryId}`);
  }
  if (!("deceased" in profile)) {
    const context = "baby" in profile
      ? { category_id: categoryId, ...profile }
      : { category_id: categoryId, marriage: profile };
    return request<IntakeConfirmation>("/api/cases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ life_event: { type: categoryId, context } }),
    });
  }

  const profilePeople = [profile.deceased, ...profile.surviving_members];
  const savedFamily = await Promise.all(
    profilePeople.map((person, index) =>
      addFamilyMember({
        name: person.name,
        relationship: person.relationship,
        is_deceased: index === 0,
        source: "intake",
      }),
    ),
  );
  const selected = subject && subject !== "self" ? subject : null;
  const people = selected && !profilePeople.some((person) => person.name === selected.name)
    ? [...profilePeople, selected]
    : profilePeople;
  const subjectIndex = 0;
  return request<IntakeConfirmation>("/api/cases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      life_event: {
        type: categoryId,
        context: {
          category_id: categoryId,
          deceased: {
            is_deceased: true,
            pension_status: profile.deceased.pension_status,
            was_electricity_account_holder: profile.assets.bescom,
            was_head_of_household: true,
          },
          surviving_spouse: { exists: profile.surviving_members.length > 0 },
          location: { state: profile.location.state },
          assets: profile.assets,
        },
      },
      household_profile: {
        location_city: profile.location.city,
        location_state: profile.location.state,
        people: [
          {
            ...(savedFamily[0]
              ? { id: savedFamily[0].id }
              : selected?.name === people[0].name
                ? { id: selected.id }
                : {}),
            name: people[0].name,
            relationship: people[0].relationship,
            role: null,
            is_deceased: true,
            attributes: {
              occupation: profile.deceased.occupation,
              pension_status: profile.deceased.pension_status,
            },
          },
          ...people.slice(1).map((person, index) => ({
            ...(savedFamily[index + 1] ? { id: savedFamily[index + 1].id } : {}),
            ...(selected?.name === person.name
              ? { id: selected.id }
              : "id" in person && person.id
                ? { id: person.id }
                : {}),
            name: person.name,
            relationship: person.relationship,
            role: null,
            is_deceased: false,
            attributes: {
              occupation: "occupation" in person ? person.occupation : "",
              pension_status: "pension_status" in person ? person.pension_status : "unknown",
            },
          })),
        ],
      },
      subject_person_index: subjectIndex,
      subject_relationship: people[subjectIndex].relationship,
    }),
  });
}

export function getCatalogServices(): Promise<{ services: CatalogService[] }> {
  return request("/api/catalog/services");
}

export function getFamily(signal?: AbortSignal): Promise<FamilyMember[]> {
  return request("/api/auth/me/family", { signal });
}

export function addFamilyMember(
  input: Pick<FamilyMember, "name" | "relationship"> & Partial<FamilyMember>,
): Promise<FamilyMember> {
  return request("/api/auth/me/family", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function updateFamilyMember(
  memberId: string,
  input: Partial<FamilyMember>,
): Promise<FamilyMember> {
  return request(`/api/auth/me/family/${encodeURIComponent(memberId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function removeFamilyMember(memberId: string): Promise<void> {
  return request(`/api/auth/me/family/${encodeURIComponent(memberId)}`, { method: "DELETE" });
}

export function getActiveBenefits(signal?: AbortSignal): Promise<{ benefits: ActiveBenefit[] }> {
  return request("/api/cases/benefits/active", { signal });
}

export function getBenefitOpportunities(
  signal?: AbortSignal,
): Promise<{ benefits: BenefitOpportunity[] }> {
  return request("/api/cases/benefits/eligible", { signal });
}

export function applyForBenefit(benefitId: string): Promise<{ case: { case_id: string } }> {
  return request(`/api/cases/benefits/${encodeURIComponent(benefitId)}/apply`, {
    method: "POST",
  });
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
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function getCase(caseId: string, signal?: AbortSignal): Promise<CitizenCase> {
  return request<CitizenCase>(`/api/cases/${encodeURIComponent(caseId)}`, { signal });
}

export function getCaseOverview(caseId: string, signal?: AbortSignal): Promise<CaseOverview> {
  return request<CaseOverview>(`/api/cases/${encodeURIComponent(caseId)}`, { signal });
}

export function getCases(signal?: AbortSignal): Promise<{ cases: CaseListItem[] }> {
  return request("/api/cases", { signal });
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

export function getDocuments(
  category?: string,
): Promise<{ documents_by_category: Record<string, DocEntry[]> }> {
  const qs = category ? `?category=${encodeURIComponent(category)}` : "";
  return request(`/api/docs${qs}`);
}

export function uploadDocument(payload: {
  document_type: string;
  title: string;
  proof_category: DocCategory;
  issuer?: string;
  valid_until?: string;
}): Promise<DocEntry> {
  return request<DocEntry>("/api/docs/upload", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getDocumentDetail(id: string): Promise<DocDetailEntry> {
  return request(`/api/docs/${encodeURIComponent(id)}`);
}

export function getDocumentAccessLog(id: string): Promise<{ accesses: AccessLogEntry[] }> {
  return request(`/api/docs/${encodeURIComponent(id)}/access-log`);
}

export function getNotifications(opts?: {
  type?: string;
  limit?: number;
}): Promise<{ notifications: NotificationItem[]; unread_count: number }> {
  const search = new URLSearchParams();
  if (opts?.type) search.set("type", opts.type);
  if (opts?.limit) search.set("limit", String(opts.limit));
  const qs = search.toString();
  return request(`/api/notifications${qs ? `?${qs}` : ""}`);
}

export function getDigest(week?: string): Promise<DigestResponse> {
  const qs = week ? `?week=${encodeURIComponent(week)}` : "";
  return request(`/api/notifications/digest${qs}`);
}

export function getActivity(options: {
  category?: string;
  days?: number;
  limit?: number;
  offset?: number;
  signal?: AbortSignal;
} = {}): Promise<ActivityFeedResponse> {
  const { signal, ...query } = options;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) search.set(key, String(value));
  }
  return request(`/api/notifications/activity?${search}`, { signal });
}

export function requestDataExport(): Promise<{ export_id: string; status: string }> {
  return request("/api/auth/me/export", { method: "POST" });
}

export function getDataExport(exportId: string): Promise<{ status: string; download_url?: string; detail?: string }> {
  return request(`/api/auth/me/export/${encodeURIComponent(exportId)}`);
}

export function getDocumentShares(): Promise<{ active_shares: DocumentShare[] }> {
  return request("/api/docs/shares");
}

export function revokeDocumentShare(shareId: string): Promise<{ revoked: boolean; note: string }> {
  return request(`/api/docs/shares/${encodeURIComponent(shareId)}/revoke`, { method: "POST" });
}

export function getWithdrawableApplications(): Promise<{ withdrawable: WithdrawableApplication[] }> {
  return request("/api/cases/withdrawable");
}

export function withdrawApplication(caseId: string, taskId: string): Promise<{ withdrawn: boolean; note: string }> {
  return request(`/api/cases/${encodeURIComponent(caseId)}/tasks/${encodeURIComponent(taskId)}/withdraw`, { method: "POST" });
}

export function getDeletionStatus(): Promise<DeletionStatus> {
  return request("/api/auth/me/delete/status");
}

export function requestAccountDeletion(password: string): Promise<DeletionStatus> {
  return request("/api/auth/me/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmation: "DELETE MY ACCOUNT", password }),
  });
}

export function cancelAccountDeletion(): Promise<{ cancelled: boolean; account_active: boolean }> {
  return request("/api/auth/me/delete/cancel", { method: "POST" });
}
