export type CaseStatus = "intake" | "active" | "completed" | "abandoned";

export type TaskStatus =
  | "pending"
  | "ready"
  | "in_progress"
  | "awaiting_approval"
  | "submitted"
  | "completed"
  | "failed"
  | "blocked";

export type ExternalApplicationStatus =
  | "prepared"
  | "submitted"
  | "processing"
  | "approved"
  | "rejected"
  | "error";

export type ApprovalStatus = "pending" | "approved" | "rejected";

export interface IntakePersonProfile {
  name: string;
  relationship: string;
  occupation: string;
  pension_status: "active" | "inactive" | "none" | "unknown";
}

export interface IntakeHouseholdProfile {
  deceased: IntakePersonProfile;
  surviving_members: IntakePersonProfile[];
  location: { city: string; state: string };
  assets: { bescom: boolean; ration_card: boolean; property: boolean };
}

export interface IntakeResponse {
  session_id: string;
  status: "in_progress" | "complete";
  message: string;
  profile: IntakeHouseholdProfile | null;
}

export interface IntakeConfirmation {
  case_id: string;
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
