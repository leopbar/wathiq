import { format, formatDistanceToNowStrict, parseISO } from "date-fns";
import { ar, enUS } from "date-fns/locale";
import i18n from "@/i18n";

export function isArabic(): boolean {
  return i18n.resolvedLanguage?.startsWith("ar") ?? false;
}

function localeName(): "ar-AE" | "en-US" {
  return isArabic() ? "ar-AE" : "en-US";
}

export function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const d = parseISO(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDate(value: string | null | undefined, pattern = "d MMM yyyy"): string {
  const d = parseDate(value);
  return d ? format(d, pattern, { locale: isArabic() ? ar : enUS }) : "—";
}

export function formatDateTime(value: string | null | undefined): string {
  return formatDate(value, "d MMM yyyy, HH:mm");
}

export function formatTime(value: string | null | undefined): string {
  return formatDate(value, "HH:mm:ss");
}

export function formatRelative(value: string | null | undefined): string {
  const d = parseDate(value);
  if (!d) return "—";
  return formatDistanceToNowStrict(d, {
    addSuffix: true,
    locale: isArabic() ? ar : enUS,
  });
}

export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(localeName(), {
    style: "percent",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString(localeName(), {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatUsd(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(localeName(), {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: value < 1 ? 3 : 2,
    maximumFractionDigits: value < 1 ? 3 : 2,
  }).format(value);
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return "—";
  const u = isArabic()
    ? { ms: " ملي ث", s: "ث", m: "د", h: "س" }
    : { ms: " ms", s: "s", m: "m", h: "h" };
  if (ms < 1000) return `${Math.round(ms)}${u.ms}`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)}${u.s}`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  if (minutes < 60) return `${minutes}${u.m} ${rest}${u.s}`;
  const hours = Math.floor(minutes / 60);
  return `${hours}${u.h} ${minutes % 60}${u.m}`;
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
}

/** Milliseconds until an ISO deadline; negative once the deadline has passed. */
export function msUntil(value: string | null | undefined): number | null {
  const d = parseDate(value);
  return d ? d.getTime() - Date.now() : null;
}

export function formatCountdown(ms: number): string {
  const abs = Math.abs(ms);
  const totalMinutes = Math.floor(abs / 60_000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours >= 24) {
    const days = Math.floor(hours / 24);
    return isArabic() ? `${days}ي ${hours % 24}س` : `${days}d ${hours % 24}h`;
  }
  if (hours > 0) return isArabic() ? `${hours}س ${minutes}د` : `${hours}h ${minutes}m`;
  return isArabic() ? `${minutes}د` : `${minutes}m`;
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Picks the Arabic variant of a bilingual API value when the interface is in Arabic and the
 * API sent one; otherwise the English value.
 */
export function localized(en: string, ar: string | null | undefined): string {
  return isArabic() && ar ? ar : en;
}
