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

export default function Settings() {
  const { role } = useAuth();
  const readOnly = isReadOnly(role) || role === "supervisor";

  return (
    <div className="space-y-4">
      <PageHeader
        title="Settings"
        description="Document types, users, the process layer, integrations and the run mode of this deployment."
        actions={readOnly ? <Badge tone="info">Read-only for your role</Badge> : null}
      />

      <Tabs
        items={[
          { value: "document-types", label: "Document types", content: <DocumentTypesTab /> },
          { value: "users", label: "Users", content: <UsersTab /> },
          { value: "assurance", label: "Assurance", content: <AssuranceTab /> },
          { value: "process", label: "Process", content: <ProcessTab /> },
          { value: "integrations", label: "Integrations", content: <IntegrationsTab /> },
          { value: "mode", label: "Mode", content: <ModeTab /> },
        ]}
      />
    </div>
  );
}
