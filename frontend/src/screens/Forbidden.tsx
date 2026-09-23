import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ShieldAlert } from "lucide-react";
import { Card } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/EmptyState";
import { useAuth } from "@/auth/useAuth";
import type { Capability } from "@/auth/roles";

/** Capabilities that have a screen name of their own; the rest read as "This screen". */
const NAMED: Capability[] = [
  "case.create",
  "review",
  "quality",
  "prompts",
  "settings",
  "settings.users",
  "audit",
];

export default function Forbidden({ capability }: { capability?: Capability }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const screen =
    capability && NAMED.includes(capability)
      ? t(`forbidden.capability.${capability.replace(".", "_")}`)
      : t("forbidden.thisScreen");

  return (
    <Card className="mx-auto max-w-xl">
      <EmptyState
        icon={ShieldAlert}
        title={t("states.forbiddenTitle")}
        description={t("forbidden.description", { screen })}
        action={
          <div className="flex flex-col items-center gap-3">
            {user ? (
              <Badge tone="primary">
                {t("forbidden.signedInAs", { role: t(`roles.${user.role}`) })}
              </Badge>
            ) : null}
            <Link to="/" className={buttonVariants({ variant: "primary" })}>
              {t("common.backToDashboard")}
            </Link>
          </div>
        }
      />
    </Card>
  );
}
