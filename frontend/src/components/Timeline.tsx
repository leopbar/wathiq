import { Bot, Cog, User as UserIcon } from "lucide-react";
import type { ActorType, TimelineEvent } from "@/lib/types";
import { formatDateTime, formatDuration } from "@/lib/format";
import { Badge } from "./ui/badge";

const ACTOR_ICON: Record<ActorType, typeof Bot> = {
  agent: Bot,
  user: UserIcon,
  system: Cog,
};

const ACTOR_STYLE: Record<ActorType, string> = {
  agent: "bg-primary-soft text-primary border-primary/30",
  user: "bg-info-soft text-info border-info/30",
  system: "bg-surface-2 text-ink-2 border-border",
};

export function Timeline({ events }: { events: TimelineEvent[] }) {
  return (
    <ol className="relative space-y-0">
      {events.map((event, index) => {
        const Icon = ACTOR_ICON[event.actor_type];
        const isLast = index === events.length - 1;
        return (
          <li key={event.id} className="relative flex gap-3 ps-0">
            <div className="flex flex-col items-center">
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border ${ACTOR_STYLE[event.actor_type]}`}
              >
                <Icon className="h-3.5 w-3.5" aria-hidden />
              </span>
              {!isLast ? <span className="w-px flex-1 bg-border" aria-hidden /> : null}
            </div>
            <div className="min-w-0 flex-1 pb-5">
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                <p className="text-body font-medium text-ink">{event.label}</p>
                <span className="text-caption text-ink-2 tabular">
                  {formatDateTime(event.created_at)}
                </span>
              </div>
              <p className="mt-0.5 text-small text-ink-2">
                <span className="font-medium text-ink-2">{event.actor}</span>
                <span className="mx-1.5 text-border" aria-hidden>
                  ·
                </span>
                <code className="text-caption">{event.action}</code>
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {event.prompt_version ? (
                  <Badge tone="outline" title="Prompt version used for this step">
                    prompt {event.prompt_version}
                  </Badge>
                ) : null}
                {event.model_version ? (
                  <Badge tone="outline" title="Model version used for this step">
                    model {event.model_version}
                  </Badge>
                ) : null}
                {event.duration_ms !== null ? (
                  <Badge tone="neutral">{formatDuration(event.duration_ms)}</Badge>
                ) : null}
              </div>
              {event.detail && Object.keys(event.detail).length > 0 ? (
                <details className="mt-2">
                  <summary className="cursor-pointer text-caption text-ink-2 hover:text-ink">
                    Detail
                  </summary>
                  <pre
                    dir="ltr"
                    className="scroll-thin mt-1.5 max-h-52 overflow-auto rounded-[var(--radius-sm)] border border-border bg-surface-2 p-2.5 text-caption leading-5"
                  >
                    {JSON.stringify(event.detail, null, 2)}
                  </pre>
                </details>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
