import { useTranslation } from "react-i18next";
import { Dialog } from "@/components/ui/dialog";

const SHORTCUTS: { keys: string; action: string }[] = [
  { keys: "A", action: "approve" },
  { keys: "C", action: "correct" },
  { keys: "R", action: "reject" },
  { keys: "E", action: "escalate" },
  { keys: "J / K", action: "move" },
  { keys: "Enter", action: "edit" },
  { keys: "?", action: "help" },
  { keys: "Esc", action: "close" },
];

export function ShortcutHelp({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={t("reviewTask.shortcuts.title")}
      description={t("reviewTask.shortcuts.description")}
    >
      <dl className="divide-y divide-border">
        {SHORTCUTS.map((shortcut) => (
          <div key={shortcut.keys} className="flex items-center gap-4 py-2">
            <dt className="w-24 shrink-0">
              <kbd
                dir="ltr"
                className="rounded border border-border bg-surface-2 px-1.5 py-0.5 text-caption font-semibold text-ink"
              >
                {shortcut.keys}
              </kbd>
            </dt>
            <dd className="text-small text-ink-2">
              {t(`reviewTask.shortcuts.actions.${shortcut.action}`)}
            </dd>
          </div>
        ))}
      </dl>
    </Dialog>
  );
}
