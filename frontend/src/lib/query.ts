import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./api";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
        return failureCount < 2;
      },
    },
    mutations: { retry: false },
  },
});

export const qk = {
  me: ["auth", "me"] as const,
  demoUsers: ["auth", "demo-users"] as const,
  mode: ["settings", "mode"] as const,
  kpis: ["dashboard", "kpis"] as const,
  charts: ["dashboard", "charts"] as const,
  cases: (params: unknown) => ["cases", "list", params] as const,
  caseDetail: (id: string) => ["cases", "detail", id] as const,
  caseAssurance: (id: string) => ["cases", "assurance", id] as const,
  caseProcess: (id: string) => ["cases", "process", id] as const,
  reviewQueue: (params: unknown) => ["review", "queue", params] as const,
  reviewTask: (id: string) => ["review", "task", id] as const,
  reasonCodes: ["review", "reason-codes"] as const,
  qualitySummary: ["quality", "summary"] as const,
  qualityRuns: (band: string | undefined) => ["quality", "runs", band ?? "all"] as const,
  qualityRun: (id: string) => ["quality", "run", id] as const,
  calibration: ["quality", "calibration"] as const,
  prompts: ["prompts", "list"] as const,
  promptVersions: (key: string) => ["prompts", "versions", key] as const,
  promptDiff: (key: string, from: string, to: string) => ["prompts", "diff", key, from, to] as const,
  documentTypes: ["settings", "document-types"] as const,
  integrations: ["settings", "integrations"] as const,
  azure: ["settings", "azure"] as const,
  authConfig: ["auth", "config"] as const,
  assurance: ["settings", "assurance"] as const,
  users: ["settings", "users"] as const,
  audit: (params: unknown) => ["audit", params] as const,
  processHealth: ["process", "health"] as const,
  auditIntegrity: ["process", "audit-integrity"] as const,
  systemInfo: ["system", "info"] as const,
  systemGraph: ["system", "graph"] as const,
};
