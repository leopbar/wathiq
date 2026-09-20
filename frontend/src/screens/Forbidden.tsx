import { Link } from "react-router-dom";
import { ShieldAlert } from "lucide-react";
import { Card } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/EmptyState";
import { useAuth } from "@/auth/useAuth";
import { ROLE_LABEL } from "@/lib/constants";
import type { Capability } from "@/auth/roles";

const CAPABILITY_LABEL: Partial<Record<Capability, string>> = {
  "case.create": "Create a case",
  review: "Review workspace",
  quality: "Quality Lab",
  prompts: "Prompt Studio",
  settings: "Settings",
  "settings.users": "User administration",
  audit: "Audit log",
};

export default function Forbidden({ capability }: { capability?: Capability }) {
  const { user } = useAuth();
  const screen = capability ? (CAPABILITY_LABEL[capability] ?? "This screen") : "This screen";

  return (
    <Card className="mx-auto max-w-xl">
      <EmptyState
        icon={ShieldAlert}
        title="Not allowed for your role"
        description={`${screen} is restricted. Access is enforced by the API as well as the interface, so nothing is hidden only on the client.`}
        action={
          <div className="flex flex-col items-center gap-3">
            {user ? (
              <Badge tone="primary">Signed in as {ROLE_LABEL[user.role]}</Badge>
            ) : null}
            <Link to="/" className={buttonVariants({ variant: "primary" })}>
              Back to dashboard
            </Link>
          </div>
        }
      />
    </Card>
  );
}
