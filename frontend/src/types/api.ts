export type CaseStatus = "intake" | "active" | "completed" | "abandoned";

export type TaskStatus =
  | "pending"
  | "ready"
  | "in_progress"
  | "awaiting_approval"
  | "submitted"
  | "completed"
  | "failed"
  | "blocked"
  | "cancelled";

export type ExternalApplicationStatus =
  | "prepared"
  | "submitted"
  | "processing"
  | "approved"
  | "rejected"
  | "error";

export type ApprovalStatus = "pending" | "approved" | "rejected";

export interface IntakePersonProfile {
  id?: string;
  name: string;
  relationship: string;
  occupation: string;
  pension_status: "active" | "inactive" | "none" | "unknown";
}

export interface FamilyMember {
  id: string;
  name: string;
  relationship: string;
  date_of_birth: string | null;
  phone: string | null;
  is_deceased: boolean;
  death_date: string | null;
  source: "manual" | "intake";
  created_at: string;
  updated_at: string;
}

export interface IntakeHouseholdProfile {
  deceased: IntakePersonProfile;
  surviving_members: IntakePersonProfile[];
  location: { city: string; state: string };
  assets: { bescom: boolean; ration_card: boolean; property: boolean };
}

export interface IntakeResponse {
  conversation_id: string;
  status: "in_progress" | "complete";
  message: string;
  profile: IntakeHouseholdProfile | null;
}

export interface IntakeConfirmation {
  case_id: string;
}

export interface AuthSession {
  user_id: string;
  username: string;
  name: string | null;
  date_of_birth?: string | null;
  city?: string | null;
  phone?: string | null;
}

export interface LifeEventCategory {
  id: string;
  title: string;
  subtitle: string;
  icon: string;
  description: string;
  service_count: number;
}

export interface CatalogService {
  id: string;
  name: string;
  authority: string;
  category: string;
  typical_wait_days: [number, number];
  stages_known: boolean;
  workflow_id: string;
}

export interface ProfileSource {
  type: string;
  reference?: string | null;
  verified: boolean;
}

export interface BenefitRuleResult {
  field: string;
  operator: string;
  expected: unknown;
  actual: unknown;
  status: "satisfied" | "failed" | "unknown";
  source: ProfileSource | null;
}

export interface BenefitOpportunity {
  id: string;
  name: string;
  description: string;
  authority: string;
  amount: string;
  source: string;
  eligibility: {
    status: "eligible" | "partially_eligible";
    rule_results: BenefitRuleResult[];
    missing_profile_fields: string[];
  };
  readiness: {
    percentage: number;
    profile: { complete: number; total: number; missing: string[] };
    documents: { available: string[]; total: number; missing: string[] };
  };
}

export interface ActiveBenefit {
  benefit_id: string;
  name: string;
  authority: string;
  amount: string;
  status: string;
  started_at: string;
  next_payment_at: string | null;
  case_id: string;
}

export interface CaseTask {
  task_id: string;
  case_id: string;
  workflow_id: string;
  task_type: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  completed_at: string | null;
  blocked_reason: string | null;
  blocked_by_task_ids: string[];
  wait_state?: {
    stages_known: boolean;
    stages: Array<{ id: string; label: string; description: string; order: number }>;
    current_stage: string | null;
    status_label: string | null;
    submitted_at: string | null;
    estimated_wait: { min_days: number | null; max_days: number | null };
    last_update: string | null;
    is_overdue: boolean;
    message: string | null;
  } | null;
  wait_summary?: string | null;
}

export interface CaseOverview {
  case_id: string;
  title: string;
  status: CaseStatus;
  life_event_type: string;
  my_role: string;
  my_permissions: string[];
  limitations: string[];
  subject: { person_id: string | null; name: string; relationship: string } | null;
  progress: { completed: number; total: number };
  created_at: string;
  updated_at: string;
  tasks_by_group: {
    ready: CaseTask[];
    waiting: CaseTask[];
    blocked: CaseTask[];
    completed: CaseTask[];
  };
}

export interface CaseListItem {
  case_id: string;
  title: string;
  status: CaseStatus;
  life_event_type: string;
  my_role: string;
  progress: { completed: number; total: number };
  created_at: string;
  updated_at: string;
}

export interface RemediationAction {
  action: "add_task";
  workflow_id: string;
  dependency_target: string;
}

export interface RejectionInterpretation {
  cause: string;
  explanation: string;
  confidence: number;
  remediation: RemediationAction;
}

export interface TaskDependency {
  id: string;
  created_at: string;
  updated_at: string;
  task_id: string;
  depends_on_task_id: string;
  dependency_type: string;
}

export interface Task {
  id: string;
  created_at: string;
  updated_at: string;
  case_id: string;
  workflow_id: string;
  task_type: string;
  status: TaskStatus;
  title: string;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  completed_at: string | null;
  dependencies: TaskDependency[];
  external_applications: ExternalApplication[];
  approval_requests: ApprovalRequest[];
}

export interface RequiredDocument {
  type: string;
  owner: string | null;
  description: string | null;
}

export interface DocumentRequirement extends RequiredDocument {
  status: "satisfied" | "missing";
}

export interface TaskDetail extends Task {
  description: string | null;
  required_documents: RequiredDocument[];
  produced_documents: Document[];
}

export interface ExternalApplication {
  id: string;
  created_at: string;
  updated_at: string;
  task_id: string;
  adapter_type: string;
  external_reference_id: string | null;
  status: ExternalApplicationStatus;
  request_payload: Record<string, unknown>;
  response_payload: Record<string, unknown>;
  submitted_at: string | null;
  responded_at: string | null;
}

export interface ApprovalRequest {
  id: string;
  created_at: string;
  updated_at: string;
  task_id: string;
  action_description: string;
  status: ApprovalStatus;
  context: Record<string, unknown>;
  requested_at: string;
  resolved_at: string | null;
}

export interface Document {
  id: string;
  created_at: string;
  updated_at: string;
  case_id: string;
  produced_by_task_id: string | null;
  document_type: string;
  owner_name: string;
  issuer: string | null;
  issued_at: string | null;
  verification_status: "pending" | "verified" | "rejected";
  extracted_fields: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export type DocCategory = "identity" | "certificates" | "address" | "income" | "family";
export type DocProvenanceType = "platform_issued" | "user_uploaded" | "digilocker" | "auto_fetched";
export type DocVerification = "pending" | "verified" | "expired" | "rejected";

export interface DocEntry {
  id: string;
  document_type: string;
  proof_category: DocCategory;
  title: string;
  issuer: string | null;
  issued_at: string | null;
  valid_from: string | null;
  valid_until: string | null;
  verification_status: DocVerification;
  provenance_type: DocProvenanceType;
  provenance_source: string | null;
  source_case_id: string | null;
  source_task_id: string | null;
  extracted_fields: Record<string, unknown>;
  metadata: Record<string, unknown>;
  superseded_by_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccessLogEntry {
  id: string;
  action: "viewed" | "shared" | "submitted" | "downloaded";
  purpose: string | null;
  recipient: string | null;
  case_id: string | null;
  task_id: string | null;
  accessed_at: string;
}

export interface DocDetailEntry extends DocEntry {
  usage_history: AccessLogEntry[];
}

export interface NotificationItem {
  id: string;
  user_id: string;
  notification_type: string;
  priority: "urgent" | "normal" | "low";
  title: string;
  body: string;
  data: Record<string, unknown>;
  read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface DigestResponse {
  week: string;
  ready_actions: NotificationItem[];
  new_opportunities: NotificationItem[];
  status_updates: NotificationItem[];
  completions: NotificationItem[];
}

export interface ActivityEntry {
  id: string;
  activity_type: string;
  title: string;
  description: string | null;
  icon: string;
  category: string;
  case_id: string | null;
  task_id: string | null;
  document_id: string | null;
  data: Record<string, unknown>;
  occurred_at: string;
}

export interface ActivityFeedResponse {
  activities: ActivityEntry[];
  groups: Array<{ date: string; activities: ActivityEntry[] }>;
  has_more: boolean;
}

export interface DocumentShare {
  share_id: string;
  document_id: string;
  document_title: string;
  shared_with: string | null;
  purpose: string | null;
  shared_at: string;
  case_id: string | null;
  task_id: string | null;
}

export interface WithdrawableApplication {
  task_id: string;
  case_id: string;
  title: string;
  authority: string;
  submitted_at: string;
  can_withdraw: boolean;
  withdrawal_note: string;
}

export interface DeletionStatus {
  status: "cooling_off" | "scheduled" | "none";
  cooling_off_until?: string;
}

export interface LifeEvent {
  id: string;
  event_type: string;
  context: Record<string, unknown>;
  occurred_at: string;
}

export interface CitizenCase {
  id: string;
  created_at: string;
  updated_at: string;
  status: CaseStatus;
  life_event: LifeEvent | null;
  household_profile: unknown | null;
  tasks: Task[];
  documents: Document[];
  audit_entries: unknown[];
}
