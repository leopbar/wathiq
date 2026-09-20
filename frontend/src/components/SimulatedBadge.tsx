import { FlaskConical, Link2, PlugZap, PowerOff } from "lucide-react";
import type { IntegrationStatus } from "@/lib/types";
import { Badge } from "./ui/badge";
import { Tooltip } from "./ui/tooltip";

const MAP: Record<
  IntegrationStatus,
  { tone: "success" | "warning" | "info" | "outline"; label: string; hint: string }
> = {
  connected: {
    tone: "success",
    label: "Connected",
    hint: "Live service — real calls leave this machine.",
  },
  simulated: {
    tone: "warning",
    label: "Simulated",
    hint: "Simulated service — no real external system is contacted.",
  },
  demo: {
    tone: "info",
    label: "Demo",
    hint: "Demo implementation with synthetic data, safe to show.",
  },
  disabled: {
    tone: "outline",
    label: "Disabled",
    hint: "Switched off in this configuration.",
  },
};

const ICON: Record<IntegrationStatus, typeof FlaskConical> = {
  connected: Link2,
  simulated: FlaskConical,
  demo: PlugZap,
  disabled: PowerOff,
};

export function SimulatedBadge({ status }: { status: IntegrationStatus }) {
  const { tone, label, hint } = MAP[status];
  const Icon = ICON[status];
  return (
    <Tooltip content={hint}>
      <span className="inline-flex">
        <Badge tone={tone}>
          <Icon className="h-3 w-3" aria-hidden />
          {label}
        </Badge>
      </span>
    </Tooltip>
  );
}
