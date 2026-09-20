import { AlertTriangle, RefreshCw } from "lucide-react";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Button } from "./ui/button";

export function describeError(error: unknown): { message: string; code?: string } {
  if (error instanceof ApiError) return { message: error.detail, code: error.code };
  if (error instanceof Error) return { message: error.message };
  return { message: "Unexpected error." };
}

export function ErrorState({
  error,
  onRetry,
  title = "Something went wrong",
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
  className?: string;
}) {
  const { message, code } = describeError(error);

  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-3 px-6 py-14 text-center",
        className,
      )}
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-danger-soft text-danger">
        <AlertTriangle className="h-5 w-5" aria-hidden />
      </span>
      <div>
        <p className="text-body font-medium text-ink">{title}</p>
        <p className="mx-auto mt-1 max-w-md text-small text-ink-2">{message}</p>
        {code ? <p className="mt-1 text-caption text-ink-2/70 tabular">{code}</p> : null}
      </div>
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RefreshCw className="h-4 w-4" aria-hidden />
          Retry
        </Button>
      ) : null}
    </div>
  );
}
