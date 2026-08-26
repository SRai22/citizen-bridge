"use client";

import Link from "next/link";
import type { ReactNode } from "react";

const button = "inline-flex items-center justify-center rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2";
const secondary = "inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 transition hover:bg-slate-50";

export function LoadingState({ label }: { label: string }) {
  return (
    <div className="grid min-h-[55vh] place-items-center" role="status">
      <div className="text-center">
        <span className="mx-auto block size-8 animate-spin rounded-full border-2 border-slate-200 border-t-cyan-700" />
        <p className="mt-4 text-sm font-medium text-slate-600">{label}</p>
      </div>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <GuidanceState icon="😔" title="Something went wrong" description={safeErrorMessage(message)} actions={<>{onRetry ? <button className={button} onClick={onRetry} type="button">Try again</button> : null}<button className={secondary} onClick={() => history.back()} type="button">Go back</button></>} footer={<span>If this keeps happening, <SupportLink />.</span>} />
  );
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: { label: string; href: string } }) {
  return <section className="rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-sm sm:p-10"><span aria-hidden="true" className="mx-auto grid size-11 place-items-center rounded-full bg-teal-50 text-xl">○</span><h2 className="mt-4 text-lg font-bold text-slate-950">{title}</h2><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-600">{description}</p>{action ? <Link className={`${button} mt-6`} href={action.href}>{action.label}</Link> : null}</section>;
}

export function TimeoutState({ system }: { system: string }) {
  return <GuidanceState icon="⏳" title={`${system} is taking longer than expected`} description="This sometimes happens with government systems. Your request has been saved — we'll try again automatically." detail="You can safely close this page. We'll notify you when it goes through." actions={<Link className={secondary} href="/applications">View applications</Link>} compact />;
}

export function SessionExpiredState() {
  return <GuidanceState icon="🔒" title="Your session has expired" description="For security, sessions expire after inactivity. Your progress has been saved." actions={<Link className={button} href="/onboarding">Log in again</Link>} />;
}

export function DeadlinePassedState({ name, deadline }: { name: string; deadline: string }) {
  return <GuidanceState icon="⚠️" title={`The deadline for ${name} has passed`} description={`The deadline was ${deadline}.`} detail="Check whether a late submission is accepted, or find an alternative service." actions={<><Link className={button} href="/services">Find another service</Link><SupportLink className={secondary} /></>} />;
}

export function AuthorityErrorState({ role, person, authority }: { role: string; person: string; authority: string }) {
  return <GuidanceState icon="🔒" title="Additional authorization needed" description={`This action requires ${authority}. You're currently ${role} for ${person}.`} detail="Ask the person to authorize the action, or provide legal authority before continuing." actions={<><Link className={button} href="/family">Manage authorization</Link><SupportLink className={secondary} /></>} compact />;
}

export function ExpiredDocumentState({ documentName, expired, requiredFor }: { documentName: string; expired: string; requiredFor?: string }) {
  return <GuidanceState icon="⚠️" title={`Your ${documentName} has expired`} description={`Expired ${expired}.${requiredFor ? ` This document is required for ${requiredFor}.` : ""}`} actions={<><Link className={button} href="/services">Renew this document →</Link><Link className={secondary} href="/documents#upload">Upload a newer version</Link></>} compact />;
}

export function InlineFieldError({ id, children }: { id: string; children: ReactNode }) {
  return <p className="mt-2 text-sm font-medium text-rose-700" id={id} role="alert">↳ {children}</p>;
}

function GuidanceState({ icon, title, description, detail, actions, footer, compact = false }: { icon: string; title: string; description: string; detail?: string; actions: ReactNode; footer?: ReactNode; compact?: boolean }) {
  return <section className={`mx-auto rounded-3xl border border-amber-200 bg-white text-center shadow-sm ${compact ? "p-5" : "mt-20 max-w-lg p-8"}`} role="alert"><span aria-hidden="true" className="mx-auto grid size-11 place-items-center rounded-full bg-amber-50 text-xl">{icon}</span><h1 className="mt-4 text-xl font-bold text-slate-950">{title}</h1><p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>{detail ? <p className="mt-2 text-sm leading-6 text-slate-500">{detail}</p> : null}<div className="mt-6 flex flex-wrap justify-center gap-3">{actions}</div>{footer ? <p className="mt-5 text-xs text-slate-500">{footer}</p> : null}</section>;
}

function SupportLink({ className = "font-bold text-teal-700 hover:text-teal-900" }: { className?: string }) {
  return <a className={className} href="mailto:support@citizenbridge.in">I need help</a>;
}

function safeErrorMessage(message: string): string {
  return /\b(?:HTTP|status|code)\s*[:#-]?\s*\d{3}\b|\b[A-Z][A-Z0-9_]{3,}\b/.test(message)
    ? "We couldn't complete your request right now. This is usually temporary."
    : message;
}
