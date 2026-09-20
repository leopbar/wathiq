import { Skeleton } from "./ui/skeleton";
import { Card } from "./ui/card";
import { TableWrap } from "./ui/table";

export function TableSkeleton({ rows = 8, cols = 6 }: { rows?: number; cols?: number }) {
  return (
    <TableWrap aria-busy="true">
      <div className="flex gap-4 border-b border-border bg-surface-2 px-3 py-3">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-3 flex-1" />
        ))}
      </div>
      <div className="divide-y divide-border">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="flex items-center gap-4 px-3 py-3.5">
            {Array.from({ length: cols }).map((_, c) => (
              <Skeleton key={c} className="h-4 flex-1" style={{ opacity: 1 - c * 0.06 }} />
            ))}
          </div>
        ))}
      </div>
    </TableWrap>
  );
}

export function StatCardSkeleton() {
  return (
    <Card className="p-4">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="mt-3 h-7 w-20" />
      <Skeleton className="mt-3 h-3 w-16" />
    </Card>
  );
}

export function ChartSkeleton({ height = 260 }: { height?: number }) {
  return (
    <div className="p-5" style={{ height }} aria-busy="true">
      <Skeleton className="h-3 w-32" />
      <div className="mt-6 flex h-[calc(100%-2.5rem)] items-end gap-2">
        {[0.5, 0.8, 0.35, 0.65, 0.9, 0.45, 0.72, 0.58, 0.85, 0.4].map((h, i) => (
          <Skeleton key={i} className="flex-1" style={{ height: `${h * 100}%` }} />
        ))}
      </div>
    </div>
  );
}

export function ListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3 p-5" aria-busy="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="h-8 w-8 rounded-full" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3.5 w-1/2" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function DetailSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-4 w-96" />
      <div className="grid gap-4 lg:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Card key={i} className="p-5">
            <Skeleton className="h-3 w-24" />
            <div className="mt-4 space-y-2">
              {[0, 1, 2, 3, 4].map((j) => (
                <Skeleton key={j} className="h-4 w-full" />
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
