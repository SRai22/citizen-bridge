import Link from "next/link";

import { formatDate, titleCase } from "@/lib/presentation";
import type { CitizenCase, DocumentRequirement } from "@/types/api";

export function DocumentsPanel({
  citizenCase,
  requirementsByTask,
}: {
  citizenCase: CitizenCase;
  requirementsByTask: Record<string, DocumentRequirement[]>;
}) {
  const tasksById = new Map(citizenCase.tasks.map((task) => [task.id, task]));

  return (
    <section className="mt-10" aria-labelledby="documents-heading">
      <div className="mb-4 flex items-center gap-3">
        <h2 id="documents-heading" className="text-2xl font-bold tracking-tight">
          Documents
        </h2>
        <span
          className="rounded-full bg-cyan-50 px-2.5 py-1 text-xs font-bold text-cyan-800"
          aria-label={`${citizenCase.documents.length} ${citizenCase.documents.length === 1 ? "document" : "documents"}`}
        >
          {citizenCase.documents.length}
        </span>
      </div>

      {citizenCase.documents.length ? (
        <ul className="grid gap-4 sm:grid-cols-2">
          {citizenCase.documents.map((document) => {
            const producer = document.produced_by_task_id
              ? tasksById.get(document.produced_by_task_id)
              : undefined;
            const consumers = citizenCase.tasks.filter((task) => {
              const declaredRequirement = requirementsByTask[task.id]?.some(
                (requirement) => requirement.type === document.document_type,
              );
              const dynamicDependency =
              (document.produced_by_task_id !== null &&
                task.dependencies.some(
                  (dependency) => dependency.depends_on_task_id === document.produced_by_task_id,
                ));
              return declaredRequirement || dynamicDependency;
            });
            const status = document.verification_status;
            const icon = status === "verified" ? "✅" : status === "pending" ? "⏳" : "🔴";

            return (
              <li
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
                key={document.id}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-bold text-slate-950">
                      {titleCase(document.document_type)}
                    </h3>
                    <p className="mt-1 text-sm text-slate-500">Owner: {document.owner_name}</p>
                  </div>
                  <span
                    className="text-xs font-bold capitalize text-slate-700"
                    aria-label={`Status: ${status}`}
                  >
                    <span aria-hidden="true">{icon}</span> {status}
                  </span>
                </div>
                <dl className="mt-4 grid gap-2 text-sm">
                  <div>
                    <dt className="inline font-semibold text-slate-700">Issuer: </dt>
                    <dd className="inline text-slate-600">{document.issuer ?? "Not recorded"}</dd>
                  </div>
                  <div>
                    <dt className="inline font-semibold text-slate-700">Issued: </dt>
                    <dd className="inline text-slate-600">
                      {document.issued_at ? formatDate(document.issued_at) : "Not issued yet"}
                    </dd>
                  </div>
                </dl>
                <div className="mt-4 border-t border-slate-100 pt-3 text-xs leading-5 text-slate-500">
                  <p>
                    Produced by →{" "}
                    {producer ? (
                      <Link
                        className="font-semibold text-cyan-800 hover:text-cyan-950"
                        href={`/case/${citizenCase.id}/task/${producer.id}`}
                      >
                        {producer.title}
                      </Link>
                    ) : (
                      "Provided by the household"
                    )}
                  </p>
                  <p>
                    Satisfies →{" "}
                    {consumers.length
                      ? consumers.map((task, index) => (
                          <span key={task.id}>
                            {index ? ", " : ""}
                            <Link
                              className="font-semibold text-cyan-800 hover:text-cyan-950"
                              href={`/case/${citizenCase.id}/task/${task.id}`}
                            >
                              {task.title}
                            </Link>
                          </span>
                        ))
                      : "No active task requirements"}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-600">
          No documents have been obtained yet.
        </div>
      )}
    </section>
  );
}
