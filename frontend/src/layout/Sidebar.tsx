import { NavLink, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { cn } from "@/lib/cn";
import { can } from "@/auth/roles";
import { useAuth } from "@/auth/useAuth";
import { BrandMark } from "@/components/BrandMark";
import { Tooltip } from "@/components/ui/tooltip";
import { NAV_GROUPS } from "./nav";

export function SidebarContent({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const { t } = useTranslation();
  const { role } = useAuth();
  const { pathname } = useLocation();

  return (
    <nav className="flex-1 space-y-5 overflow-y-auto scroll-thin px-3 py-4" aria-label="Main">
      {NAV_GROUPS.map((group) => {
        const items = group.items.filter((item) => can(role, item.capability));
        if (items.length === 0) return null;
        return (
          <div key={group.labelKey}>
            {!collapsed ? (
              <p className="label-caption px-2 pb-1.5 text-ink-2">{t(group.labelKey)}</p>
            ) : (
              <div className="mx-2 mb-2 border-t border-border" aria-hidden />
            )}
            <ul className="space-y-0.5">
              {items.map((item) => {
                const label = t(item.labelKey);
                const link = (
                  <NavLink
                    to={item.to}
                    end={item.end}
                    onClick={onNavigate}
                    aria-label={collapsed ? label : undefined}
                    className={({ isActive }) => {
                      const active = item.activeWhen ? item.activeWhen(pathname) : isActive;
                      return cn(
                        "flex items-center gap-2.5 rounded-[var(--radius)] px-2.5 py-2 text-body font-medium transition-colors",
                        collapsed && "justify-center px-0",
                        active
                          ? "bg-primary-soft text-primary"
                          : "text-ink-2 hover:bg-surface-2 hover:text-ink",
                      );
                    }}
                  >
                    <item.icon className="h-4 w-4 shrink-0" aria-hidden />
                    {!collapsed ? <span className="truncate">{label}</span> : null}
                  </NavLink>
                );

                return (
                  <li key={item.to}>
                    {collapsed ? (
                      <Tooltip content={label} side="right">
                        {link}
                      </Tooltip>
                    ) : (
                      link
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const { t } = useTranslation();

  return (
    <aside
      className={cn(
        "fixed inset-y-0 start-0 z-30 hidden flex-col border-e border-border bg-surface transition-[width] duration-200 lg:flex",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <div
        className={cn(
          "flex h-14 items-center gap-2.5 border-b border-border px-4",
          collapsed && "justify-center px-0",
        )}
      >
        <BrandMark className="text-primary" size={24} />
        {!collapsed ? (
          <div className="leading-tight">
            <p className="text-body font-semibold tracking-tight text-ink">Wathiq</p>
            <p className="text-caption text-ink-2">{t("brand.tagline")}</p>
          </div>
        ) : null}
      </div>

      <SidebarContent collapsed={collapsed} />

      <div className="border-t border-border p-2">
        <button
          type="button"
          onClick={onToggle}
          aria-label={t("common.toggleSidebar")}
          aria-expanded={!collapsed}
          className={cn(
            "flex w-full items-center gap-2.5 rounded-[var(--radius)] px-2.5 py-2 text-small text-ink-2 hover:bg-surface-2 hover:text-ink",
            collapsed && "justify-center px-0",
          )}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-4 w-4 rtl:rotate-180" aria-hidden />
          ) : (
            <>
              <PanelLeftClose className="h-4 w-4 rtl:rotate-180" aria-hidden />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
