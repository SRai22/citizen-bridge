import type { CitizenCase, RequiredDocument, Task, TaskStatus } from "@/types/api";

export function titleCase(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((word) => `${word.charAt(0).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

export function caseTitle(citizenCase: CitizenCase): string {
  const suppliedTitle = citizenCase.life_event?.context.title;
  if (typeof suppliedTitle === "string" && suppliedTitle.trim()) return suppliedTitle;
  if (citizenCase.life_event) return `${titleCase(citizenCase.life_event.event_type)} case`;
  return "Citizen support case";
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function dependencySummary(task: Task, tasks: Task[]): string {
  if (task.dependencies.length === 0) return "No prerequisites";
  const tasksById = new Map(tasks.map((candidate) => [candidate.id, candidate]));
  const dependencies = task.dependencies.map(
    (dependency) => tasksById.get(dependency.depends_on_task_id)?.title ?? "Another task",
  );
  const incomplete = task.dependencies.filter(
    (dependency) => tasksById.get(dependency.depends_on_task_id)?.status !== "completed",
  );
  const prefix = task.status === "blocked"
    ? "Blocked by"
    : incomplete.length
      ? "Waiting on"
      : "Prerequisite complete";
  return `${prefix}: ${dependencies.join(", ")}`;
}

export function statusMessage(status: TaskStatus): string {
  const messages: Record<TaskStatus, string> = {
    pending: "This task will become available when its prerequisites are complete.",
    ready: "This task is ready for you to begin.",
    in_progress: "Work on this task is currently in progress.",
    awaiting_approval: "Review and approval are needed before submission.",
    submitted: "The application has been sent to the responsible authority.",
    completed: "This task has been completed successfully.",
    failed: "The latest attempt was unsuccessful and needs attention.",
    blocked: "A newly identified prerequisite must be completed first.",
  };
  return messages[status];
}

export function documentLabel(document: RequiredDocument): string {
  return titleCase(document.type);
}
