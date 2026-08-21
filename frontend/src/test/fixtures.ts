import type { CitizenCase, Document, Task, TaskDetail, TaskStatus } from "@/types/api";

const timestamp = "2026-08-15T12:00:00Z";

export function makeTask(
  overrides: Partial<Task> & Pick<Task, "id" | "title">,
): Task {
  const { id, title, ...rest } = overrides;
  return {
    id,
    title,
    created_at: timestamp,
    updated_at: timestamp,
    case_id: "case-12345678",
    workflow_id: "death_certificate",
    task_type: "death_registration",
    status: "pending" as TaskStatus,
    input_data: {},
    output_data: {},
    completed_at: null,
    dependencies: [],
    external_applications: [],
    approval_requests: [],
    ...rest,
  };
}

export const completedTask = makeTask({
  id: "task-death",
  title: "Obtain Death Certificate",
  status: "completed",
  completed_at: timestamp,
});

export const pendingTask = makeTask({
  id: "task-pension",
  title: "Apply for Family Pension",
  workflow_id: "family_pension",
  task_type: "family_pension_application",
  dependencies: [
    {
      id: "dependency-1",
      created_at: timestamp,
      updated_at: timestamp,
      task_id: "task-pension",
      depends_on_task_id: "task-death",
      dependency_type: "completion",
    },
  ],
});

export const deathCertificate: Document = {
  id: "document-death",
  created_at: timestamp,
  updated_at: timestamp,
  case_id: "case-12345678",
  produced_by_task_id: completedTask.id,
  document_type: "death_certificate",
  owner_name: "Arun Rao",
  issuer: "BBMP South Zone",
  issued_at: timestamp,
  verification_status: "verified",
  extracted_fields: {},
  metadata: {},
};

export const citizenCase: CitizenCase = {
  id: "case-12345678",
  created_at: timestamp,
  updated_at: timestamp,
  status: "active",
  life_event: {
    id: "event-1",
    event_type: "parent_death",
    context: {},
    occurred_at: timestamp,
  },
  household_profile: null,
  tasks: [completedTask, pendingTask],
  documents: [],
  audit_entries: [],
};

export const taskDetail: TaskDetail = {
  ...pendingTask,
  description: "Transfer the deceased pensioner's family pension to the surviving spouse.",
  required_documents: [
    {
      type: "death_certificate",
      owner: "deceased",
      description: "Official death certificate for the deceased pensioner.",
    },
  ],
  produced_documents: [],
};
