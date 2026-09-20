import { cn } from "@/lib/cn";
import { EmptyState } from "@/components/EmptyState";

function lineTone(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---")) return "text-ink-2";
  if (line.startsWith("@@")) return "bg-info-soft text-info";
  if (line.startsWith("+")) return "bg-success-soft text-success";
  if (line.startsWith("-")) return "bg-danger-soft text-danger";
  return "text-ink-2";
}

export function DiffViewer({ diff }: { diff: string }) {
  const lines = diff.split("\n");
  if (lines.length === 0 || diff.trim() === "") {
    return (
      <EmptyState
        title="No differences"
        description="These two versions have identical prompt bodies."
      />
    );
  }

  return (
    <div className="overflow-hidden rounded-[var(--radius)] border border-border">
      <pre
        dir="ltr"
        className="scroll-thin max-h-[26rem] overflow-auto bg-surface text-caption leading-5"
      >
        <code>
          {lines.map((line, index) => (
            <span
              key={index}
              className={cn("block whitespace-pre-wrap px-3 py-px", lineTone(line))}
            >
              {line || " "}
            </span>
          ))}
        </code>
      </pre>
    </div>
  );
}
