import { Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "./ui/button";
import { Tooltip } from "./ui/tooltip";
import { useTheme } from "./useTheme";

export function ThemeToggle() {
  const { t } = useTranslation();
  const { theme, toggle } = useTheme();
  const label = theme === "dark" ? t("common.themeLight") : t("common.themeDark");

  return (
    <Tooltip content={label}>
      <Button variant="ghost" size="icon" onClick={toggle} aria-label={label}>
        {theme === "dark" ? (
          <Sun className="h-4 w-4" aria-hidden />
        ) : (
          <Moon className="h-4 w-4" aria-hidden />
        )}
      </Button>
    </Tooltip>
  );
}
