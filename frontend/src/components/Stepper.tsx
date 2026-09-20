import { Check, CircleDashed, Loader2, PauseCircle, X } from "lucide-react";
import { cn } from "@/lib/cn";

/**
 * `waiting` is not the same as `active`: the graph is parked at the review gate and nothing
 * will move until a person answers. Showing a spinner there would suggest the system is busy
 * when it is actually waiting on the user.
 */
export type StepState = "pending" | "active" | "waiting" | "done" | "failed";

export interface StepperStep {
  key: string;
  label: string;
  description: string;
  state: StepState;
  message?: string;
}

const ICON: Record<StepState, typeof Check> = {
  pending: CircleDashed,
  active: Loader2,
  waiting: PauseCircle,
  done: Check,
  failed: X,
};

const RING: Record<StepState, string> = {
  pending: "border-border bg-surface text-ink-2/70",
  active: "border-primary bg-primary-soft text-primary",
  waiting: "border-warning bg-warning-soft text-warning",
  done: "border-success bg-success-soft text-success",
  failed: "border-danger bg-danger-soft text-danger",
};

export function Stepper({ steps }: { steps: StepperStep[] }) {
  return (
    <ol className="space-y-0" aria-label="Pipeline progress">
      {steps.map((step, index) => {
        const Icon = ICON[step.state];
        const isLast = index === steps.length - 1;
        return (
          <li key={step.key} className="flex gap-3">
            <div className="flex flex-col items-center">
              <span
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
                  RING[step.state],
                )}
              >
                <Icon
                  className={cn("h-4 w-4", step.state === "active" && "animate-spin")}
                  aria-hidden
                />
              </span>
              {!isLast ? (
                <span
                  className={cn(
                    "w-0.5 flex-1 transition-colors",
                    step.state === "done" ? "bg-success/50" : "bg-border",
                  )}
                  aria-hidden
                />
              ) : null}
            </div>
            <div className={cn("min-w-0 flex-1", isLast ? "pb-0" : "pb-6")}>
              <p
                className={cn(
                  "text-body font-medium",
                  step.state === "pending" ? "text-ink-2" : "text-ink",
                )}
              >
                {step.label}
                <span className="sr-only"> — {step.state}</span>
              </p>
              <p className="mt-0.5 text-small text-ink-2">{step.message ?? step.description}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
