"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useState } from "react";

import { logout } from "@/lib/api";

export const navigation = [
  { href: "/services", label: "My Services", icon: "⌂" },
  { href: "/documents", label: "My Documents", icon: "▤" },
  { href: "/benefits", label: "My Benefits", icon: "◇" },
  { href: "/applications", label: "My Applications", icon: "✓" },
  { href: "/family", label: "My Family", icon: "♧" },
  { href: "/life-events", label: "Active Life Events", icon: "◎" },
  { href: "/activity", label: "Recent Activity", icon: "↻" },
  { href: "/profile", label: "My Profile", icon: "♙" },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  if (["/", "/login", "/register", "/onboarding"].includes(pathname) || pathname.endsWith("/review")) return children;

  return (
    <div className="min-h-screen bg-slate-50 md:flex">
      <SideNav collapsed={collapsed} onCollapse={() => setCollapsed(!collapsed)} />
      <MobileDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-8">
          <button
            aria-controls="mobile-navigation"
            aria-expanded={drawerOpen}
            aria-label="Open navigation"
            className="grid size-11 place-items-center rounded-xl border border-slate-200 text-xl text-slate-800 md:hidden"
            onClick={() => setDrawerOpen(true)}
            type="button"
          >
            ☰
          </button>
          {pathname !== "/" ? <button aria-label="Go back" className="rounded-xl px-3 py-2 text-sm font-bold text-slate-700 hover:bg-slate-100" onClick={() => router.back()} type="button">← Back</button> : null}
          <div className="md:hidden"><Brand compact /></div>
          <Link className="ml-auto rounded-xl px-3 py-2 text-sm font-bold text-teal-800 hover:bg-teal-50" href="/profile">My Profile</Link>
        </header>
        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-8 sm:py-9">{children}</main>
      </div>
    </div>
  );
}

export function SideNav({
  collapsed,
  onCollapse,
}: {
  collapsed: boolean;
  onCollapse: () => void;
}) {
  return (
    <aside
      className={`sticky top-0 hidden h-screen shrink-0 flex-col border-r border-slate-200 bg-slate-950 text-white transition-[width] duration-200 md:flex ${collapsed ? "w-20" : "w-64"}`}
    >
      <div className="flex h-20 items-center border-b border-white/10 px-4">
        <Brand compact={collapsed} inverse />
      </div>
      <nav aria-label="Primary navigation" className="flex-1 space-y-1 px-3 py-5">
        {navigation.map((item) => (
          <NavItem collapsed={collapsed} item={item} key={item.href} />
        ))}
      </nav>
      <AccountActions collapsed={collapsed} />
      <button
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        className="m-3 rounded-xl border border-white/15 px-3 py-2 text-sm text-slate-300 hover:bg-white/10 hover:text-white"
        onClick={onCollapse}
        type="button"
      >
        {collapsed ? "→" : "← Collapse"}
      </button>
    </aside>
  );
}

export function MobileDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <div
      aria-hidden={!open}
      className={`fixed inset-0 z-40 md:hidden ${open ? "pointer-events-auto" : "pointer-events-none"}`}
    >
      <button
        aria-label="Close navigation"
        className={`absolute inset-0 bg-slate-950/45 transition-opacity ${open ? "opacity-100" : "opacity-0"}`}
        onClick={onClose}
        tabIndex={open ? 0 : -1}
        type="button"
      />
      <aside
        className={`relative flex h-full w-[min(84vw,20rem)] flex-col bg-slate-950 p-4 text-white shadow-2xl transition-transform duration-200 ${open ? "translate-x-0" : "-translate-x-full"}`}
        id="mobile-navigation"
      >
        <div className="flex h-14 items-center justify-between">
          <Brand inverse />
          <button
            aria-label="Close navigation"
            className="grid size-10 place-items-center rounded-xl text-xl text-slate-300 hover:bg-white/10"
            onClick={onClose}
            type="button"
          >
            ×
          </button>
        </div>
        <nav aria-label="Mobile navigation" className="mt-5 flex-1 space-y-1">
          {navigation.map((item) => (
            <NavItem item={item} key={item.href} onNavigate={onClose} />
          ))}
        </nav>
        <AccountActions onNavigate={onClose} />
      </aside>
    </div>
  );
}

function AccountActions({ collapsed = false, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function signOut() {
    setBusy(true);
    try {
      await logout();
    } catch {
      // Local logout must still work while the auth service is unavailable.
    } finally {
      localStorage.removeItem("citizen-bridge:onboarding");
      onNavigate?.();
      router.replace("/");
      router.refresh();
    }
  }

  return <button className="mx-3 flex min-h-12 items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-300 hover:bg-white/10 hover:text-white disabled:opacity-60" disabled={busy} onClick={() => void signOut()} title={collapsed ? "Log out" : undefined} type="button"><span aria-hidden="true" className="grid size-7 shrink-0 place-items-center text-lg">↪</span>{collapsed ? <span className="sr-only">Log out</span> : <span>{busy ? "Logging out…" : "Log out"}</span>}</button>;
}

export function NavItem({
  item,
  collapsed = false,
  onNavigate,
}: {
  item: (typeof navigation)[number];
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const lifeEventRoute = item.href === "/life-events" && pathname.startsWith("/case/");
  const active =
    lifeEventRoute ||
    pathname.startsWith(item.href);
  return (
    <Link
      aria-current={active ? "page" : undefined}
      className={`flex min-h-12 items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition ${active ? "bg-teal-600 text-white" : "text-slate-300 hover:bg-white/10 hover:text-white"}`}
      href={item.href}
      onClick={onNavigate}
      title={collapsed ? item.label : undefined}
    >
      <span aria-hidden="true" className="grid size-7 shrink-0 place-items-center text-lg">
        {item.icon}
      </span>
      {collapsed ? <span className="sr-only">{item.label}</span> : <span>{item.label}</span>}
    </Link>
  );
}

function Brand({ compact = false, inverse = false }: { compact?: boolean; inverse?: boolean }) {
  return (
    <Link
      aria-label="Citizen Bridge home"
      className={`flex items-center gap-3 font-bold tracking-tight ${inverse ? "text-white" : "text-slate-950"}`}
      href="/"
    >
      <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-teal-600 text-sm text-white">
        CB
      </span>
      {compact ? null : <span className={inverse ? "rounded-lg bg-white px-2 py-1" : undefined}><Image alt="JanSetu" className={inverse ? "h-7 w-auto" : "h-8 w-auto"} height={32} priority src="/citizen-bridge-logo.png" width={96} /></span>}
    </Link>
  );
}
