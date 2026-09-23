import { FlaskConical, Link2, PlugZap, PowerOff } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { IntegrationStatus } from "@/lib/types";
import { Badge } from "./ui/badge";
import { Tooltip } from "./ui/tooltip";

const TONE: Record<IntegrationStatus, "success" | "warning" | "info" | "outline"> = {
  connected: "success",
  simulated: "warning",
  demo: "info",
  disabled: "outline",
};

const ICON: Record<IntegrationStatus, typeof FlaskConical> = {
  connected: Link2,
  simulated: FlaskConical,
  demo: PlugZap,
  disabled: PowerOff,
};

export function SimulatedBadge({ status }: { status: IntegrationStatus }) {
  const { t } = useTranslation();
  const Icon = ICON[status];
  return (
    <Tooltip content={t(`integrationStatus.${status}.hint`)}>
      <span className="inline-flex">
        <Badge tone={TONE[status]}>
          <Icon className="h-3 w-3" aria-hidden />
          {t(`integrationStatus.${status}.label`)}
        </Badge>
      </span>
    </Tooltip>
  );
}
