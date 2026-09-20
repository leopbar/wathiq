import type { LucideIcon } from "lucide-react";
import {
  BookOpenCheck,
  FileStack,
  FilePlus2,
  FlaskConical,
  Gauge,
  Info,
  ScrollText,
  Settings,
  Sparkles,
} from "lucide-react";
import type { Capability } from "@/auth/roles";

export interface NavItem {
  to: string;
  labelKey: string;
  icon: LucideIcon;
  capability: Capability;
  end?: boolean;
  /** Overrides NavLink's own matching where prefixes overlap (/cases vs /cases/new). */
  activeWhen?: (pathname: string) => boolean;
}

export interface NavGroup {
  labelKey: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    labelKey: "nav.groupWork",
    items: [
      { to: "/", labelKey: "nav.dashboard", icon: Gauge, capability: "dashboard", end: true },
      {
        to: "/cases",
        labelKey: "nav.cases",
        icon: FileStack,
        capability: "cases",
        activeWhen: (pathname) => pathname.startsWith("/cases") && pathname !== "/cases/new",
      },
      { to: "/cases/new", labelKey: "nav.newCase", icon: FilePlus2, capability: "case.create" },
      { to: "/review", labelKey: "nav.review", icon: BookOpenCheck, capability: "review" },
    ],
  },
  {
    labelKey: "nav.groupAssurance",
    items: [
      { to: "/quality", labelKey: "nav.quality", icon: FlaskConical, capability: "quality" },
      { to: "/prompts", labelKey: "nav.prompts", icon: Sparkles, capability: "prompts" },
      { to: "/audit", labelKey: "nav.audit", icon: ScrollText, capability: "audit" },
    ],
  },
  {
    labelKey: "nav.groupSystem",
    items: [
      { to: "/settings", labelKey: "nav.settings", icon: Settings, capability: "settings" },
      { to: "/about", labelKey: "nav.about", icon: Info, capability: "about" },
    ],
  },
];
