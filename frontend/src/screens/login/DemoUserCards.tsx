import type { LucideIcon } from "lucide-react";
import { ClipboardCheck, Eye, ShieldCheck, UserCog, Users } from "lucide-react";
import type { DemoUser, Role } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

const ROLE_ICON: Record<Role, LucideIcon> = {
  ops_officer: ClipboardCheck,
  reviewer: Users,
  supervisor: ShieldCheck,
  admin: UserCog,
  auditor: Eye,
};

export function DemoUserSkeleton() {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {[0, 1, 2, 3, 4].map((i) => (
        <Skeleton key={i} className="h-16 w-full rounded-[var(--radius)]" />
      ))}
    </div>
  );
}

export function DemoUserCards({
  users,
  onSelect,
  pendingRole,
  disabled,
}: {
  users: DemoUser[];
  onSelect: (role: Role) => void;
  pendingRole: Role | null;
  disabled: boolean;
}) {
  return (
    <ul className="grid gap-2 sm:grid-cols-2">
      {users.map((user) => {
        const Icon = ROLE_ICON[user.role];
        const busy = pendingRole === user.role;
        return (
          <li key={user.role}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onSelect(user.role)}
              aria-busy={busy}
              aria-label={`Sign in as ${user.title}`}
              className="group flex h-full w-full items-start gap-3 rounded-[var(--radius)] border border-border bg-surface p-3 text-start transition-colors hover:border-primary/40 hover:bg-primary-soft/40 disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            >
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-sm)] bg-primary-soft text-primary">
                <Icon className="h-4 w-4" aria-hidden />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-small font-semibold text-ink">
                  {user.title}
                </span>
                <span className="mt-0.5 block text-caption leading-4 text-ink-2">
                  {user.description}
                </span>
                <span className="mt-1 block truncate text-caption text-ink-2/80" dir="ltr">
                  {busy ? "Signing in…" : user.email}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
