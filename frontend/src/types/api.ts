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
  external_applications: unknown[];
  approval_requests: unknown[];
}

export interface RequiredDocument {
  type: string;
  owner: string | null;
  description: string | null;
}

export interface TaskDetail extends Task {
  description: string | null;
  required_documents: RequiredDocument[];
  produced_documents: unknown[];
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
  documents: unknown[];
  audit_entries: unknown[];
}
