import { Link } from "react-router-dom";
import { Ban } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function suspendedDetail() {
  try {
    return JSON.parse(sessionStorage.getItem("signguy.suspended") || "{}");
  } catch {
    return {};
  }
}

export default function AccountSuspendedPage() {
  const detail = suspendedDetail();
  return (
    <div className="min-h-dvh grid place-items-center px-4 py-10 header-wash" data-testid="account-suspended-page">
      <Card className="w-full max-w-[460px]">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-lg bg-destructive text-destructive-foreground">
              <Ban className="size-5" />
            </div>
            <CardTitle>Account Suspended</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-muted-foreground">
          <p>{detail.message || "This shop account is suspended. Contact SignGuy AI support."}</p>
          {detail.reason && <p className="rounded border bg-muted px-3 py-2 text-foreground">{detail.reason}</p>}
          <p>Contact: <a className="link-underline" href={`mailto:${detail.support_email || "support@signguy.ai"}`}>{detail.support_email || "support@signguy.ai"}</a></p>
          <Button asChild variant="outline">
            <Link to="/login">Back to sign in</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
