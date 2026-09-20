import { useQuery } from "@tanstack/react-query";
import { FileCog, ShieldAlert } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { qk } from "@/lib/query";
import type { DocumentTypeConfig } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { ListSkeleton } from "@/components/Skeletons";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";

function SchemaTable({ config }: { config: DocumentTypeConfig }) {
  return (
    <TableWrap className="border-0">
      <Table>
        <caption className="sr-only">Schema fields for {config.name_en}</caption>
        <thead>
          <tr>
            <Th>Field</Th>
            <Th>Label (EN)</Th>
            <Th>Label (AR)</Th>
            <Th>Type</Th>
            <Th>Rules</Th>
          </tr>
        </thead>
        <tbody>
          {config.fields.map((field) => (
            <Tr key={field.name}>
              <Td>
                <code className="text-caption text-ink">{field.name}</code>
              </Td>
              <Td className="text-small">{field.label_en}</Td>
              <Td className="text-small" dir="rtl">
                {field.label_ar}
              </Td>
              <Td>
                <Badge tone="outline">{field.type}</Badge>
              </Td>
              <Td>
                <span className="flex flex-wrap gap-1.5">
                  {field.required ? <Badge tone="info">required</Badge> : null}
                  {field.is_critical ? (
                    <Badge tone="danger">
                      <ShieldAlert className="h-3 w-3" aria-hidden />
                      critical
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
        title="No document types configured"
        description="A document type is a schema, a prompt, a rule set and a golden set — nothing in the engine changes when one is added."
      />
    );
  }

  return (
    <div className="space-y-4 pt-4">
      <p className="text-small text-ink-2">
        Adding a document type is configuration only: schema, prompt, cross-field rules and a golden
        set. The extraction engine does not change.
      </p>
      {query.data.map((config) => (
        <Card key={config.id} className="overflow-hidden">
          <CardHeader
            title={
              <span className="flex flex-wrap items-center gap-2">
                {config.name_en}
                <span dir="rtl" className="text-small font-normal text-ink-2">
                  {config.name_ar}
                </span>
              </span>
            }
            description={`${config.fields.length} fields · ${config.rules_count} cross-field rules`}
            action={
              <div className="flex gap-1.5">
                <Badge tone="outline">v{config.version}</Badge>
                <Badge tone={config.is_active ? "success" : "neutral"}>
                  {config.is_active ? "active" : "inactive"}
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
