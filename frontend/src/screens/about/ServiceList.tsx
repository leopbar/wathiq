import { AlertTriangle, CheckCircle2, MinusCircle, XCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { SystemInfo } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

type ServiceStatus = SystemInfo["services"][number]["status"];

const ICON: Record<ServiceStatus, typeof CheckCircle2> = {
  healthy: CheckCircle2,
  degraded: AlertTriangle,
  down: XCircle,
  disabled: MinusCircle,
};

const TONE: Record<ServiceStatus, "success" | "warning" | "danger" | "neutral"> = {
  healthy: "success",
  degraded: "warning",
  down: "danger",
  disabled: "neutral",
};

const COLOUR: Record<ServiceStatus, string> = {
  healthy: "text-success",
  degraded: "text-warning",
  down: "text-danger",
  disabled: "text-ink-2",
};

export function ServiceList({ services }: { services: SystemInfo["services"] }) {
  const { t } = useTranslation();
  return (
    <ul className="divide-y divide-border">
      {services.map((service) => {
        const Icon = ICON[service.status];
        return (
          <li key={service.name} className="flex items-start gap-3 px-5 py-3">
            <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${COLOUR[service.status]}`} aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="truncate text-small font-medium text-ink">{service.name}</p>
              <p className="text-caption leading-4 text-ink-2">{service.detail}</p>
            </div>
            <Badge tone={TONE[service.status]}>{t(`about.serviceState.${service.status}`)}</Badge>
          </li>
        );
      })}
    </ul>
  );
}
