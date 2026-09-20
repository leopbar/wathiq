import type { Role } from "@/lib/types";

export type Capability =
  | "dashboard"
  | "cases"
  | "case.create"
  | "review"
  | "quality"
  | "quality.run"
  | "prompts"
  | "prompts.approve"
  | "settings"
  | "settings.users"
  | "audit"
  | "about";

const ALL: Role[] = ["ops_officer", "reviewer", "supervisor", "admin", "auditor"];

/** Mirrors the role-access table at the bottom of docs/API.md. */
const CAPABILITIES: Record<Capability, Role[]> = {
  dashboard: ALL,
  cases: ALL,
  "case.create": ["ops_officer", "supervisor", "admin"],
  review: ["reviewer", "supervisor", "admin"],
  quality: ["reviewer", "supervisor", "admin", "auditor"],
  "quality.run": ["supervisor", "admin"],
  prompts: ["supervisor", "admin", "auditor"],
  "prompts.approve": ["admin"],
  settings: ["supervisor", "admin", "auditor"],
  "settings.users": ["admin"],
  audit: ALL,
  about: ALL,
};

export function can(role: Role | undefined, capability: Capability): boolean {
  if (!role) return false;
  return CAPABILITIES[capability].includes(role);
}

/** Roles that see a screen but may not change anything on it. */
export function isReadOnly(role: Role | undefined): boolean {
  return role === "auditor";
}
