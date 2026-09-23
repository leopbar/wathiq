import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Compass } from "lucide-react";
import { Card } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/EmptyState";

export default function NotFound() {
  const { t } = useTranslation();
  return (
    <Card className="mx-auto max-w-xl">
      <EmptyState
        icon={Compass}
        title={t("states.notFoundTitle")}
        description={t("notFound.description")}
        action={
          <Link to="/" className={buttonVariants({ variant: "primary" })}>
            {t("common.backToDashboard")}
          </Link>
        }
      />
    </Card>
  );
}
