import { useTranslation } from "react-i18next";
import { useAuth } from "@/auth/useAuth";
import { isReadOnly } from "@/auth/roles";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Tabs } from "@/components/ui/tabs";
import { DocumentTypesTab } from "./settings/DocumentTypesTab";
import { UsersTab } from "./settings/UsersTab";
import { IntegrationsTab } from "./settings/IntegrationsTab";
import { ModeTab } from "./settings/ModeTab";
import { AssuranceTab } from "./settings/AssuranceTab";
import { ProcessTab } from "./settings/ProcessTab";
import { AzureTab } from "./settings/AzureTab";

export default function Settings() {
  const { t } = useTranslation();
  const { role } = useAuth();
  const readOnly = isReadOnly(role) || role === "supervisor";

  return (
    <div className="space-y-4">
      <PageHeader
        title={t("settings.title")}
        description={t("settings.description")}
        actions={readOnly ? <Badge tone="info">{t("settings.readOnly")}</Badge> : null}
      />

      <Tabs
        items={[
          { value: "document-types", label: t("settings.tabs.documentTypes"), content: <DocumentTypesTab /> },
          { value: "users", label: t("settings.tabs.users"), content: <UsersTab /> },
          { value: "assurance", label: t("settings.tabs.assurance"), content: <AssuranceTab /> },
          { value: "process", label: t("settings.tabs.process"), content: <ProcessTab /> },
          { value: "integrations", label: t("settings.tabs.integrations"), content: <IntegrationsTab /> },
          { value: "azure", label: t("settings.tabs.azure"), content: <AzureTab /> },
          { value: "mode", label: t("settings.tabs.mode"), content: <ModeTab /> },
        ]}
      />
    </div>
  );
}
