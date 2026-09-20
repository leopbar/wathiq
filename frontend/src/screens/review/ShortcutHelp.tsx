import { Dialog } from "@/components/ui/dialog";

const SHORTCUTS: { keys: string; action: string }[] = [
  { keys: "A", action: "Approve the case as extracted" },
  { keys: "C", action: "Record corrections and approve" },
  { keys: "R", action: "Reject the case" },
  { keys: "E", action: "Escalate to a supervisor" },
  { keys: "J / K", action: "Move to the next / previous field" },
  { keys: "Enter", action: "Edit the focused field" },
  { keys: "?", action: "Open this help" },
  { keys: "Esc", action: "Close dialogs" },
];

export function ShortcutHelp({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Keyboard shortcuts"
      description="The review workspace is fully keyboard operable."
    >
      <dl className="divide-y divide-border">
        {SHORTCUTS.map((shortcut) => (
          <div key={shortcut.keys} className="flex items-center gap-4 py-2">
            <dt className="w-24 shrink-0">
              <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5 text-caption font-semibold text-ink">
                {shortcut.keys}
              </kbd>
            </dt>
            <dd className="text-small text-ink-2">{shortcut.action}</dd>
          </div>
        ))}
      </dl>
    </Dialog>
  );
}
