import { useTranslation } from "react-i18next";
import type { SystemInfo } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";

export function StackTable({ stack }: { stack: SystemInfo["stack"] }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-4">
      {stack.map((layer) => (
        <Card key={layer.layer} className="overflow-hidden">
          <CardHeader
            title={layer.layer}
            description={t("about.stack.description")}
            action={<Badge tone="outline">{t("about.stack.choices", { count: layer.items.length })}</Badge>}
          />
          <TableWrap className="border-0">
            <Table>
              <caption className="sr-only">{t("about.stack.caption", { layer: layer.layer })}</caption>
              <thead>
                <tr>
                  <Th className="w-44">{t("about.stack.component")}</Th>
                  <Th className="w-24">{t("about.stack.version")}</Th>
                  <Th>{t("about.stack.why")}</Th>
                  <Th className="w-56">{t("about.stack.alternative")}</Th>
                </tr>
              </thead>
              <tbody>
                {layer.items.map((item) => (
                  <Tr key={`${layer.layer}-${item.name}`}>
                    <Td className="text-small font-medium text-ink">{item.name}</Td>
                    <Td>
                      <code className="text-caption text-ink-2" dir="ltr">
                        {item.version}
                      </code>
                    </Td>
                    <Td className="text-small text-ink-2">{item.why}</Td>
                    <Td className="text-small text-ink-2">{item.alternative}</Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        </Card>
      ))}
    </div>
  );
}
