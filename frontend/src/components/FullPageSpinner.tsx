import { Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

export function FullPageSpinner({ label }: { label?: string }) {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-[60vh] items-center justify-center" role="status" aria-live="polite">
      <Loader2 className="h-6 w-6 animate-spin text-primary" aria-hidden />
      <span className="sr-only">{label ?? t("common.loading")}</span>
    </div>
  );
}
