import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import { Card } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/EmptyState";

export default function NotFound() {
  return (
    <Card className="mx-auto max-w-xl">
      <EmptyState
        icon={Compass}
        title="Page not found"
        description="That route does not exist in Wathiq. It may have been renamed, or the link is out of date."
        action={
          <Link to="/" className={buttonVariants({ variant: "primary" })}>
            Back to dashboard
          </Link>
        }
      />
    </Card>
  );
}
