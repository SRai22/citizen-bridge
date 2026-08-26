"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { ErrorState, LoadingState } from "@/components/page-state";
import {
  ApiError, cancelAccountDeletion, getDataExport, getDeletionStatus,
  getDocumentShares, getWithdrawableApplications, requestAccountDeletion,
  requestDataExport, revokeDocumentShare, withdrawApplication,
} from "@/lib/api";
import type { DeletionStatus, DocumentShare, WithdrawableApplication } from "@/types/api";

export default function DataControlsPage() {
  const [shares, setShares] = useState<DocumentShare[] | null>(null);
  const [applications, setApplications] = useState<WithdrawableApplication[] | null>(null);
  const [deletion, setDeletion] = useState<DeletionStatus | null>(null);
  const [exportState, setExportState] = useState<{ id: string; status: string; url?: string } | null>(null);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getDocumentShares(), getWithdrawableApplications(), getDeletionStatus()])
      .then(([shareData, applicationData, deletionData]) => {
        setShares(shareData.active_shares);
        setApplications(applicationData.withdrawable);
        setDeletion(deletionData);
      })
      .catch((reason: unknown) => setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong."));
  }, []);

  useEffect(() => {
    if (!exportState || exportState.status !== "processing") return;
    const timer = window.setInterval(() => getDataExport(exportState.id).then((result) => {
      if (result.status !== "processing") {
        setExportState({ id: exportState.id, status: result.status, url: result.download_url });
      }
    }).catch(() => setExportState({ id: exportState.id, status: "failed" })), 1_000);
    return () => window.clearInterval(timer);
  }, [exportState]);

  async function startExport() {
    const result = await requestDataExport();
    setExportState({ id: result.export_id, status: result.status });
  }

  async function revoke(share: DocumentShare) {
    const result = await revokeDocumentShare(share.share_id);
    setShares((current) => current?.filter((item) => item.share_id !== share.share_id) ?? []);
    setMessage(result.note);
  }

  async function withdraw(application: WithdrawableApplication) {
    const result = await withdrawApplication(application.case_id, application.task_id);
    setApplications((current) => current?.filter((item) => item.task_id !== application.task_id) ?? []);
    setMessage(result.note);
  }

  async function deleteAccount(event: FormEvent) {
    event.preventDefault();
    if (confirmation !== "DELETE MY ACCOUNT") return;
    setDeletion(await requestAccountDeletion(password));
    setPassword(""); setConfirmation("");
  }

  async function cancelDeletion() {
    await cancelAccountDeletion();
    setDeletion({ status: "none" });
    setMessage("Account deletion cancelled. Your account remains active.");
  }

  if (error) return <ErrorState message={error} />;
  if (!shares || !applications || !deletion) return <LoadingState label="Loading your data controls…" />;

  return (
    <div className="mx-auto max-w-3xl py-2 sm:py-3">
      <header className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Settings</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-950">My Data Controls</h1>
        <p className="mt-3 text-sm text-slate-500">You control your data. These actions appear in your <Link className="font-bold text-teal-700" href="/activity">activity history</Link>.</p>
      </header>

      {message ? <p className="mt-4 rounded-2xl bg-teal-50 p-4 text-sm text-teal-900" role="status">{message}</p> : null}

      <Control title="Download my data" description="Export your profile, family, documents, cases, activity, notifications, grants, and sharing history as human-readable JSON.">
        {exportState?.status === "ready" && exportState.url ? <a className={primaryButton} href={exportState.url}>Download JSON</a> : <button className={primaryButton} disabled={exportState?.status === "processing"} onClick={() => startExport().catch(showError(setError))} type="button">{exportState?.status === "processing" ? "Preparing…" : exportState?.status === "failed" ? "Try again" : "Prepare export"}</button>}
      </Control>

      <Control title="Revoke document sharing" description="Stop future platform sharing. Copies already received by a government body cannot be recalled.">
        {shares.length ? <ul className="mt-4 space-y-3">{shares.map((share) => <li className="flex flex-col justify-between gap-3 rounded-xl bg-slate-50 p-4 sm:flex-row sm:items-center" key={share.share_id}><div><p className="font-semibold text-slate-900">{share.document_title}</p><p className="text-sm text-slate-500">{share.shared_with} · {share.purpose}</p></div><button className={secondaryButton} onClick={() => revoke(share).catch(showError(setError))} type="button">Revoke</button></li>)}</ul> : <p className="mt-3 text-sm text-slate-500">No active document shares.</p>}
      </Control>

      <Control title="Withdraw active applications" description="Request withdrawal before an authority approves or processes an application.">
        {applications.length ? <ul className="mt-4 space-y-3">{applications.map((application) => <li className="flex flex-col justify-between gap-3 rounded-xl bg-slate-50 p-4 sm:flex-row sm:items-center" key={application.task_id}><div><p className="font-semibold text-slate-900">{application.title}</p><p className="text-sm text-slate-500">{application.authority}</p></div><button className={secondaryButton} disabled={!application.can_withdraw} onClick={() => withdraw(application).catch(showError(setError))} type="button">Withdraw</button></li>)}</ul> : <p className="mt-3 text-sm text-slate-500">No submitted applications can be withdrawn.</p>}
      </Control>

      <Control destructive title="Delete my account" description="After a 7-day cooling-off period, platform data is deleted. Government submissions, issued certificates, and data already shared cannot be recalled.">
        {deletion.status === "cooling_off" ? <div className="mt-4"><p className="text-sm text-red-800">Scheduled after {new Date(deletion.cooling_off_until!).toLocaleString("en-IN")}</p><button className={secondaryButton} onClick={() => cancelDeletion().catch(showError(setError))} type="button">Cancel deletion</button></div> : <form className="mt-4 space-y-3" onSubmit={deleteAccount}><label className="block text-sm font-semibold text-slate-700">Re-enter password<input className="mt-1 block w-full rounded-xl border border-slate-300 px-3 py-2" onChange={(event) => setPassword(event.target.value)} required type="password" value={password} /></label><label className="block text-sm font-semibold text-slate-700">Type DELETE MY ACCOUNT<input className="mt-1 block w-full rounded-xl border border-slate-300 px-3 py-2" onChange={(event) => setConfirmation(event.target.value)} required value={confirmation} /></label><button className="rounded-xl border border-red-300 px-4 py-2.5 text-sm font-bold text-red-700 disabled:opacity-50" disabled={confirmation !== "DELETE MY ACCOUNT"} type="submit">Start 7-day cooling-off</button></form>}
      </Control>
    </div>
  );
}

function Control({ children, description, destructive, title }: { children: React.ReactNode; description: string; destructive?: boolean; title: string }) {
  return <section className="mt-5 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"><h2 className={`text-lg font-bold ${destructive ? "text-red-700" : "text-slate-950"}`}>{title}</h2><p className="mt-1 text-sm text-slate-500">{description}</p>{children}</section>;
}

function showError(setError: (message: string) => void) { return (reason: unknown) => setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong."); }
const primaryButton = "inline-block rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50";
const secondaryButton = "mt-2 shrink-0 rounded-xl border border-slate-300 px-4 py-2 text-sm font-bold text-slate-700 disabled:opacity-50 sm:mt-0";
