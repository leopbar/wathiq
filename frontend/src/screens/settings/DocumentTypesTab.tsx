import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { FileCog, ShieldAlert } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { qk } from "@/lib/query";
import { localized } from "@/lib/format";
import type { DocumentTypeConfig } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { ListSkeleton } from "@/components/Skeletons";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";

function SchemaTable({ config }: { config: DocumentTypeConfig }) {
  const { t } = useTranslation();
  return (
    <TableWrap className="border-0">
      <Table>
        <caption className="sr-only">
          {t("settings.documentTypes.schemaCaption", {
            name: localized(config.name_en, config.name_ar),
          })}
        </caption>
        <thead>
          <tr>
            <Th>{t("settings.documentTypes.columns.field")}</Th>
            <Th>{t("settings.documentTypes.columns.labelEn")}</Th>
            <Th>{t("settings.documentTypes.columns.labelAr")}</Th>
            <Th>{t("settings.documentTypes.columns.type")}</Th>
            <Th>{t("settings.documentTypes.columns.rules")}</Th>
          </tr>
        </thead>
        <tbody>
          {config.fields.map((field) => (
            <Tr key={field.name}>
              <Td>
                <code className="text-caption text-ink" dir="ltr">
                  {field.name}
                </code>
              </Td>
              <Td className="text-small" dir="ltr">
                {field.label_en}
              </Td>
              <Td className="text-small" dir="rtl">
                {field.label_ar}
              </Td>
              <Td>
                <Badge tone="outline">
                  <bdi>{field.type}</bdi>
                </Badge>
              </Td>
              <Td>
                <span className="flex flex-wrap gap-1.5">
                  {field.required ? (
                    <Badge tone="info">{t("settings.documentTypes.required")}</Badge>
                  ) : null}
                  {field.is_critical ? (
                    <Badge tone="danger">
                      <ShieldAlert className="h-3 w-3" aria-hidden />
                      {t("settings.documentTypes.critical")}
                    </Badge>
                  ) : null}
                </span>
              </Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}

export function DocumentTypesTab() {
  const { t, i18n } = useTranslation();
  const arabic = i18n.language.startsWith("ar");
  const query = useQuery({
    queryKey: qk.documentTypes,
    queryFn: () => apiFetch<DocumentTypeConfig[]>("/settings/document-types"),
  });

  if (query.isPending) return <ListSkeleton rows={4} />;
  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }
  if (query.data.length === 0) {
    return (
      <EmptyState
        icon={FileCog}
        title={t("settings.documentTypes.emptyTitle")}
        description={t("settings.documentTypes.emptyDescription")}
      />
    );
  }

  return (
    <div className="space-y-4 pt-4">
      <p className="text-small text-ink-2">{t("settings.documentTypes.intro")}</p>
      {query.data.map((config) => (
        <Card key={config.id} className="overflow-hidden">
          <CardHeader
            title={
              <span className="flex flex-wrap items-center gap-2">
                {arabic ? config.name_ar : config.name_en}
                <span
                  dir={arabic ? "ltr" : "rtl"}
                  className="text-small font-normal text-ink-2"
                >
                  {arabic ? config.name_en : config.name_ar}
                </span>
              </span>
            }
            description={`${t("settings.documentTypes.fields", {
              count: config.fields.length,
            })} · ${t("settings.documentTypes.crossFieldRules", { count: config.rules_count })}`}
            action={
              <div className="flex gap-1.5">
                <Badge tone="outline">
                  <bdi>v{config.version}</bdi>
                </Badge>
                <Badge tone={config.is_active ? "success" : "neutral"}>
                  {config.is_active
                    ? t("settings.documentTypes.active")
                    : t("settings.documentTypes.inactive")}
                </Badge>
              </div>
            }
          />
          <SchemaTable config={config} />
        </Card>
      ))}
    </div>
  );
}
