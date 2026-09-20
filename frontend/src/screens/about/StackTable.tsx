import type { SystemInfo } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";

export function StackTable({ stack }: { stack: SystemInfo["stack"] }) {
  return (
    <div className="space-y-4">
      {stack.map((layer) => (
        <Card key={layer.layer} className="overflow-hidden">
          <CardHeader
            title={layer.layer}
            description="What we used, and what we deliberately did not use."
            action={<Badge tone="outline">{layer.items.length} choices</Badge>}
          />
          <TableWrap className="border-0">
            <Table>
              <caption className="sr-only">{layer.layer} stack choices</caption>
              <thead>
                <tr>
                  <Th className="w-44">Component</Th>
                  <Th className="w-24">Version</Th>
                  <Th>Why we chose it</Th>
                  <Th className="w-56">Alternative considered</Th>
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
