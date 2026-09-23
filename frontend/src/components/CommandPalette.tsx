import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Dialog as RadixDialog } from "radix-ui";
import { CornerDownLeft, FileText, Search } from "lucide-react";
import { apiFetch, buildQuery } from "@/lib/api";
import type { CaseSummary, Page } from "@/lib/types";
import { can } from "@/auth/roles";
import { useAuth } from "@/auth/useAuth";
import { NAV_GROUPS } from "@/layout/nav";
import { cn } from "@/lib/cn";

interface Command {
  id: string;
  label: string;
  hint?: string;
  group: string;
  to: string;
}

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  const { role } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setActive(0);
    }
  }, [open]);

  const trimmed = query.trim();
  const { data: caseResults } = useQuery({
    queryKey: ["command", "cases", trimmed],
    queryFn: () =>
      apiFetch<Page<CaseSummary>>(`/cases${buildQuery({ q: trimmed, size: 6, page: 1 })}`),
    enabled: open && trimmed.length >= 2 && can(role, "cases"),
    staleTime: 10_000,
  });

  const commands = useMemo<Command[]>(() => {
    const navCommands: Command[] = NAV_GROUPS.flatMap((group) =>
      group.items
        .filter((item) => can(role, item.capability))
        .map((item) => ({
          id: `nav:${item.to}`,
          label: t(item.labelKey),
          group: t(group.labelKey),
          to: item.to,
        })),
    );

    const matching = trimmed
      ? navCommands.filter((c) => c.label.toLowerCase().includes(trimmed.toLowerCase()))
      : navCommands;

    const caseCommands: Command[] = (caseResults?.items ?? []).map((c) => ({
      id: `case:${c.id}`,
      label: c.reference,
      hint: c.customer_name,
      group: t("nav.cases"),
      to: `/cases/${c.id}`,
    }));

    return [...matching, ...caseCommands];
  }, [role, t, trimmed, caseResults]);

  useEffect(() => {
    setActive(0);
  }, [commands.length]);

  const run = (command: Command | undefined) => {
    if (!command) return;
    onOpenChange(false);
    navigate(command.to);
  };

  const grouped = commands.reduce<Record<string, Command[]>>((acc, command) => {
    (acc[command.group] ??= []).push(command);
    return acc;
  }, {});

  let index = -1;

  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-50 bg-[#050a12]/50 backdrop-blur-[2px]" />
        <RadixDialog.Content
          aria-label={t("common.commandPalette")}
          className="fixed left-1/2 top-[12vh] z-50 w-[min(92vw,36rem)] -translate-x-1/2 overflow-hidden rounded-[var(--radius-lg)] border border-border bg-surface shadow-pop"
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, commands.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter") {
              e.preventDefault();
              run(commands[active]);
            }
          }}
        >
          <RadixDialog.Title className="sr-only">{t("common.commandPalette")}</RadixDialog.Title>
          <RadixDialog.Description className="sr-only">
            {t("commandPalette.description")}
          </RadixDialog.Description>
          <div className="flex items-center gap-2 border-b border-border px-4">
            <Search className="h-4 w-4 shrink-0 text-ink-2" aria-hidden />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("common.searchPlaceholder")}
              aria-label={t("common.searchPlaceholder")}
              className="h-12 w-full bg-transparent text-body text-ink outline-none placeholder:text-ink-2/70"
            />
            <kbd className="hidden rounded border border-border px-1.5 py-0.5 text-caption text-ink-2 sm:block">
              Esc
            </kbd>
          </div>

          <ul ref={listRef} className="max-h-[52vh] overflow-y-auto scroll-thin p-2">
            {commands.length === 0 ? (
              <li className="px-3 py-8 text-center text-small text-ink-2">
                {t("common.noResults")}
              </li>
            ) : (
              Object.entries(grouped).map(([group, items]) => (
                <li key={group} className="mb-1">
                  <p className="label-caption px-2 py-1.5 text-ink-2">{group}</p>
                  <ul>
                    {items.map((command) => {
                      index += 1;
                      const current = index;
                      return (
                        <li key={command.id}>
                          <button
                            type="button"
                            onMouseEnter={() => setActive(current)}
                            onClick={() => run(command)}
                            aria-current={current === active}
                            className={cn(
                              "flex w-full items-center gap-2.5 rounded-[var(--radius-sm)] px-2.5 py-2 text-start text-body",
                              current === active
                                ? "bg-primary-soft text-ink"
                                : "text-ink hover:bg-surface-2",
                            )}
                          >
                            <FileText className="h-4 w-4 shrink-0 text-ink-2" aria-hidden />
                            <span className="truncate font-medium">{command.label}</span>
                            {command.hint ? (
                              <span className="truncate text-small text-ink-2">{command.hint}</span>
                            ) : null}
                            {current === active ? (
                              <CornerDownLeft
                                className="ms-auto h-3.5 w-3.5 text-ink-2"
                                aria-hidden
                              />
                            ) : null}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </li>
              ))
            )}
          </ul>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
