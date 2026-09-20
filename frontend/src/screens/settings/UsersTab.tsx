import { useQuery } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { qk } from "@/lib/query";
import type { User } from "@/lib/types";
import { ROLE_LABEL } from "@/lib/constants";
import { initials } from "@/lib/format";
import { useAuth } from "@/auth/useAuth";
import { can } from "@/auth/roles";
import { Badge } from "@/components/ui/badge";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { TableSkeleton } from "@/components/Skeletons";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";

export function UsersTab() {
  const { role } = useAuth();
  const allowed = can(role, "settings.users");

  const query = useQuery({
    queryKey: qk.users,
    queryFn: () => apiFetch<User[]>("/settings/users"),
    enabled: allowed,
  });

  if (!allowed) {
    return (
      <EmptyState
        icon={Users}
        title="Administrators only"
        description="User administration is restricted to the admin role. The API refuses this call for other roles as well."
      />
    );
  }

  if (query.isPending) return <TableSkeleton rows={5} cols={4} />;
  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }
  if (query.data.length === 0) {
    return <EmptyState icon={Users} title="No users" />;
  }

  return (
    <div className="pt-4">
      <TableWrap>
        <Table>
          <caption className="sr-only">Users and roles</caption>
          <thead>
            <tr>
              <Th>Name</Th>
              <Th>Email</Th>
              <Th>Role</Th>
              <Th>Status</Th>
            </tr>
          </thead>
          <tbody>
            {query.data.map((user) => (
              <Tr key={user.id}>
                <Td>
                  <div className="flex items-center gap-2.5">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary-soft text-caption font-semibold text-primary">
                      {initials(user.full_name)}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-small text-ink">{user.full_name}</p>
                      <p className="truncate text-caption text-ink-2" dir="rtl">
                        {user.full_name_ar}
                      </p>
                    </div>
                  </div>
                </Td>
                <Td className="text-small text-ink-2" dir="ltr">
                  {user.email}
                </Td>
                <Td>
                  <Badge tone="primary">{ROLE_LABEL[user.role]}</Badge>
                </Td>
                <Td>
                  <Badge tone={user.is_active ? "success" : "neutral"}>
                    {user.is_active ? "active" : "disabled"}
                  </Badge>
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      </TableWrap>
    </div>
  );
}
