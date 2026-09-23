import { useTranslation } from "react-i18next";
import { DropdownMenu } from "radix-ui";
import { ChevronDown, LogOut, Menu, Search, UserRound } from "lucide-react";
import { useAuth } from "@/auth/useAuth";
import { initials } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ModeBadge } from "@/components/ModeBadge";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LanguageToggle } from "@/components/LanguageToggle";

export function TopBar({
  onOpenCommand,
  onOpenNav,
}: {
  onOpenCommand: () => void;
  onOpenNav: () => void;
}) {
  const { t } = useTranslation();
  const { user, signOut } = useAuth();
  const isArabic = document.documentElement.dir === "rtl";
  const displayName = user
    ? isArabic && user.full_name_ar
      ? user.full_name_ar
      : user.full_name
    : "—";
  const roleLabel = user ? t(`roles.${user.role}`) : "";

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-border bg-surface/90 px-4 backdrop-blur">
      <Button
        variant="ghost"
        size="icon"
        className="lg:hidden"
        onClick={onOpenNav}
        aria-label={t("common.toggleSidebar")}
      >
        <Menu className="h-4 w-4" aria-hidden />
      </Button>

      <button
        type="button"
        onClick={onOpenCommand}
        className="flex h-9 w-full max-w-sm items-center gap-2 rounded-[var(--radius)] border border-border bg-surface-2/60 px-3 text-small text-ink-2 transition-colors hover:bg-surface-2"
      >
        <Search className="h-4 w-4 shrink-0" aria-hidden />
        <span className="truncate">{t("common.searchPlaceholder")}</span>
        <kbd className="ms-auto hidden rounded border border-border bg-surface px-1.5 py-0.5 text-caption sm:block">
          ⌘K
        </kbd>
      </button>

      <div className="ms-auto flex items-center gap-1.5">
        <ModeBadge />
        <LanguageToggle />
        <ThemeToggle />

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              type="button"
              className="flex items-center gap-2 rounded-[var(--radius)] px-1.5 py-1 text-start hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              aria-label={t("common.accountMenu")}
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-soft text-caption font-semibold text-primary">
                {user ? initials(displayName) : <UserRound className="h-4 w-4" aria-hidden />}
              </span>
              <span className="hidden leading-tight sm:block">
                <span className="block max-w-36 truncate text-small font-medium text-ink">
                  {displayName}
                </span>
                <span className="block text-caption text-ink-2">
                  {roleLabel}
                </span>
              </span>
              <ChevronDown className="hidden h-3.5 w-3.5 text-ink-2 sm:block" aria-hidden />
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={6}
              className="z-50 w-64 rounded-[var(--radius)] border border-border bg-surface p-1.5 shadow-pop"
            >
              <div className="px-2.5 py-2">
                <p className="truncate text-body font-medium text-ink">{displayName}</p>
                <p className="truncate text-small text-ink-2" dir="ltr">
                  {user?.email}
                </p>
                <p className="mt-1 truncate text-caption text-ink-2" dir="rtl">
                  {user?.full_name_ar}
                </p>
                {user ? (
                  <Badge tone="primary" className="mt-2">
                    {roleLabel}
                  </Badge>
                ) : null}
              </div>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Item
                onSelect={signOut}
                className="flex cursor-pointer items-center gap-2 rounded-[var(--radius-sm)] px-2.5 py-2 text-body text-ink outline-none data-[highlighted]:bg-surface-2"
              >
                <LogOut className="h-4 w-4 text-ink-2" aria-hidden />
                {t("common.signOut")}
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
    </header>
  );
}
