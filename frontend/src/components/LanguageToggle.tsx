import { useTranslation } from "react-i18next";
import { Languages } from "lucide-react";
import type { AppLang } from "@/i18n";
import { Button } from "./ui/button";
import { Tooltip } from "./ui/tooltip";

export function LanguageToggle() {
  const { i18n } = useTranslation();
  const current = (i18n.language?.startsWith("ar") ? "ar" : "en") as AppLang;
  const next: AppLang = current === "en" ? "ar" : "en";
  const label = next === "ar" ? "التبديل إلى العربية" : "Switch to English";

  const switchTo = () => {
    void i18n.changeLanguage(next);
  };

  return (
    <Tooltip content={label}>
      <Button variant="ghost" size="sm" onClick={switchTo} aria-label={label}>
        <Languages className="h-4 w-4" aria-hidden />
        <span className="text-small font-medium">{next === "ar" ? "العربية" : "EN"}</span>
      </Button>
    </Tooltip>
  );
}
