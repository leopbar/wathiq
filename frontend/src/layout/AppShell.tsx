import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Dialog as RadixDialog } from "radix-ui";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";
import { SIDEBAR_KEY } from "@/lib/constants";
import { useAuth } from "@/auth/useAuth";
import { BrandMark } from "@/components/BrandMark";
import { CommandPalette } from "@/components/CommandPalette";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { Sidebar, SidebarContent } from "./Sidebar";
import { TopBar } from "./TopBar";

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === "collapsed";
  } catch {
    return false;
  }
}

export function AppShell() {
  const { t } = useTranslation();
  const { user, isLoading } = useAuth();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [navOpen, setNavOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const toggleSidebar = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(SIDEBAR_KEY, next ? "collapsed" : "expanded");
      } catch {
        /* storage blocked */
      }
      return next;
    });
  };

  if (isLoading) return <FullPageSpinner />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;

  return (
    <div className="min-h-dvh bg-bg">
      <Sidebar collapsed={collapsed} onToggle={toggleSidebar} />

      <RadixDialog.Root open={navOpen} onOpenChange={setNavOpen}>
        <RadixDialog.Portal>
          <RadixDialog.Overlay className="fixed inset-0 z-40 bg-[#050a12]/50 lg:hidden" />
          <RadixDialog.Content className="fixed inset-y-0 start-0 z-50 flex w-64 flex-col border-e border-border bg-surface shadow-pop lg:hidden">
            <div className="flex h-14 items-center justify-between border-b border-border px-4">
              <div className="flex items-center gap-2.5">
                <BrandMark className="text-primary" size={24} />
                <RadixDialog.Title className="text-body font-semibold text-ink">
                  Wathiq
                </RadixDialog.Title>
              </div>
              <RadixDialog.Close aria-label={t("common.close")} className="p-1 text-ink-2">
                <X className="h-4 w-4" aria-hidden />
              </RadixDialog.Close>
            </div>
            <RadixDialog.Description className="sr-only">
              {t("common.mainNavigationMenu")}
            </RadixDialog.Description>
            <SidebarContent collapsed={false} onNavigate={() => setNavOpen(false)} />
          </RadixDialog.Content>
        </RadixDialog.Portal>
      </RadixDialog.Root>

      <div className={cn("transition-[padding] duration-200", collapsed ? "lg:ps-16" : "lg:ps-60")}>
        <TopBar onOpenCommand={() => setCommandOpen(true)} onOpenNav={() => setNavOpen(true)} />
        <main className="mx-auto w-full max-w-[1440px] px-4 py-6 sm:px-6">
          <Outlet />
        </main>
      </div>

      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />
    </div>
  );
}
