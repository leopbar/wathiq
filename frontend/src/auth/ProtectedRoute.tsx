import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./useAuth";
import { can, type Capability } from "./roles";
import Forbidden from "@/screens/Forbidden";
import { FullPageSpinner } from "@/components/FullPageSpinner";

export function ProtectedRoute({
  capability,
  children,
}: {
  capability: Capability;
  children: ReactNode;
}) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return <FullPageSpinner />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (!can(user.role, capability)) return <Forbidden capability={capability} />;
  return <>{children}</>;
}
