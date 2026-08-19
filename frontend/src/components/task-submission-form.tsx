"use client";

import { FormEvent, useState } from "react";

import type { TaskDetail } from "@/types/api";

export interface TaskFormField {
  name: string;
  label: string;
  type?: "text" | "date" | "textarea";
  placeholder?: string;
}

const TASK_FIELDS: Record<string, TaskFormField[]> = {
  death_registration: [
    { name: "deceased_name", label: "Full name of deceased", placeholder: "As shown on ID" },
    { name: "date_of_death", label: "Date of death", type: "date" },
    { name: "place_of_death", label: "Place of death", placeholder: "Hospital or address" },
    {
      name: "cause_of_death",
      label: "Cause of death",
      placeholder: "As stated on the medical certificate",
    },
  ],
  bescom_name_transfer: [
    { name: "consumer_number", label: "Consumer number" },
    { name: "current_holder_name", label: "Current account holder" },
    { name: "proposed_holder_name", label: "New account holder" },
    { name: "property_address", label: "Service address", type: "textarea" },
  ],
  family_pension_application: [
    { name: "spouse_name", label: "Applicant name" },
    { name: "ppo_number", label: "Existing PPO number" },
    { name: "bank_account_number", label: "Pension bank account number" },
  ],
  ration_card_modification: [
    { name: "ration_card_number", label: "Ration card number" },
    { name: "deceased_name", label: "Member to remove" },
    { name: "new_head_name", label: "New head of household" },
  ],
};

export function fieldsForTask(task: TaskDetail): TaskFormField[] {
  const configured = TASK_FIELDS[task.task_type];
  if (configured) return configured;
  const existingKeys = Object.keys(task.input_data);
  if (existingKeys.length) {
    return existingKeys.map((name) => ({
      name,
      label: name
        .split("_")
        .map((word) => `${word.charAt(0).toUpperCase()}${word.slice(1)}`)
        .join(" "),
    }));
  }
  return [{ name: "applicant_details", label: "Application details", type: "textarea" }];
}

interface TaskSubmissionFormProps {
  task: TaskDetail;
  busy: boolean;
  error: string | null;
  onSubmit: (values: Record<string, unknown>, fields: TaskFormField[]) => Promise<void>;
}

export function TaskSubmissionForm({
  task,
  busy,
  error,
  onSubmit,
}: TaskSubmissionFormProps) {
  const fields = fieldsForTask(task);
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      fields.map((field): [string, string] => {
        const existingValue = task.input_data[field.name];
        return [field.name, typeof existingValue === "string" ? existingValue : ""];
      }),
    ),
  );
  const canPrepare = task.status === "ready" || task.status === "in_progress";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canPrepare || busy) return;
    await onSubmit({ ...task.input_data, ...values }, fields);
  }

  return (
    <section
      className="border-t border-slate-200 p-6 sm:p-8"
      aria-labelledby="submission-heading"
    >
      <div className="max-w-2xl">
        <p className="text-sm font-semibold text-cyan-700">Application</p>
        <h2 id="submission-heading" className="mt-1 text-xl font-bold text-slate-950">
          Submission details
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          Review these details carefully. You will confirm the complete submission before it is
          sent.
        </p>
      </div>

      <form className="mt-6" onSubmit={handleSubmit}>
        <fieldset className="grid gap-5 sm:grid-cols-2" disabled={!canPrepare || busy}>
          <legend className="sr-only">Submission details</legend>
          {fields.map((field) => (
            <label
              className={field.type === "textarea" ? "sm:col-span-2" : undefined}
              key={field.name}
            >
              <span className="text-sm font-bold text-slate-800">{field.label}</span>
              {field.type === "textarea" ? (
                <textarea
                  className="mt-2 min-h-28 w-full resize-y rounded-xl border border-slate-300 bg-white px-3.5 py-3 text-sm text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-cyan-600 focus:ring-2 focus:ring-cyan-100 disabled:bg-slate-50"
                  name={field.name}
                  onChange={(event) =>
                    setValues((current) => ({ ...current, [field.name]: event.target.value }))
                  }
                  placeholder={field.placeholder}
                  required
                  value={values[field.name]}
                />
              ) : (
                <input
                  className="mt-2 h-11 w-full rounded-xl border border-slate-300 bg-white px-3.5 text-sm text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-cyan-600 focus:ring-2 focus:ring-cyan-100 disabled:bg-slate-50"
                  name={field.name}
                  onChange={(event) =>
                    setValues((current) => ({ ...current, [field.name]: event.target.value }))
                  }
                  placeholder={field.placeholder}
                  required
                  type={field.type ?? "text"}
                  value={values[field.name]}
                />
              )}
            </label>
          ))}
        </fieldset>

        {error ? (
          <p className="mt-5 rounded-xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-800" role="alert">
            {error}
          </p>
        ) : null}

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
          <button
            className="inline-flex min-h-11 items-center justify-center rounded-xl bg-cyan-700 px-5 text-sm font-bold text-white transition hover:bg-cyan-800 focus:outline-none focus:ring-2 focus:ring-cyan-600 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={!canPrepare || busy}
            type="submit"
          >
            {busy ? "Preparing…" : "Prepare submission"}
          </button>
          {!canPrepare ? (
            <p className="text-sm text-slate-500">This form is unavailable in the current state.</p>
          ) : null}
        </div>
      </form>
    </section>
  );
}
