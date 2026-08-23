import { Link } from "react-router-dom";
import {
  Copy,
  ExternalLink,
  Eye,
  Mail,
  RotateCcw,
  Send,
} from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function WebstoreDetailHeader({ model }) {
  const {
    formatDateTime,
    formatLabel,
    id,
    nextRequiredAction,
    ownerAssignment,
    questionnaire,
    questionnaireDelivery,
    questionnaireLink,
    relaunch,
    sendQuestionnaire,
    setupProgress,
    store,
  } = model;

return <>
      <PageHeader
        title={store.name}
        subtitle={`Webstores setup - ${formatLabel(store.webstore_type || store.store_type || "general")} - ${formatLabel(store.status)}`}
        actions={
          <div className="flex items-center gap-2 flex-wrap">
            {ownerAssignment ? (
              <Button asChild variant="outline" size="sm">
                <Link to={`/portal/webstores/${id}`}>
                  <ExternalLink className="size-4 mr-2" />
                  View Owner Setup Portal
                </Link>
              </Button>
            ) : (
              <Button variant="outline" size="sm" disabled>
                <ExternalLink className="size-4 mr-2" />
                Owner Setup Portal Not Ready
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              disabled={sendQuestionnaire.isPending || !ownerAssignment}
              onClick={() => sendQuestionnaire.mutate()}
              data-testid="webstore-send-questionnaire"
            >
              <Mail className="size-4 mr-2" />
              Send Questionnaire
            </Button>
            {["closed", "completed"].includes(store.status) && (
              <Button
                variant="outline"
                size="sm"
                disabled={relaunch.isPending}
                onClick={() => relaunch.mutate()}
                data-testid="webstore-relaunch"
              >
                <RotateCcw className="size-4 mr-2" />
                {relaunch.isPending ? "Checking..." : "Prepare Relaunch"}
              </Button>
            )}
            {store.status === "live" &&
            (store.public_url || store.public_slug || store.slug) ? (
              <Button asChild variant="outline" size="sm">
                <Link
                  to={
                    store.public_url ||
                    `/p/webstores/${store.public_slug || store.slug}`
                  }
                >
                  <Eye className="size-4 mr-2" />
                  Preview Store
                </Link>
              </Button>
            ) : (
              <Button variant="outline" size="sm" disabled>
                <Eye className="size-4 mr-2" />
                Preview Not Ready
              </Button>
            )}
          </div>
        }
      />

      {questionnaireDelivery && (
        <Alert
          variant={questionnaireDelivery.email_sent ? "default" : "destructive"}
          data-testid="webstore-questionnaire-delivery"
        >
          <Mail className="size-4" />
          <AlertTitle>
            {questionnaireDelivery.email_sent
              ? "Questionnaire sent"
              : "Questionnaire email was not sent"}
          </AlertTitle>
          <AlertDescription className="space-y-2">
            <div>
              {questionnaireDelivery.email_sent
                ? `Sent to ${questionnaireDelivery.email}.`
                : `Delivery error: ${questionnaireDelivery.delivery_error || "delivery unavailable"}.`}
            </div>
            {questionnaireLink && (
              <div className="flex flex-wrap items-center gap-2">
                <a
                  className="break-all underline"
                  href={questionnaireLink}
                  target="_blank"
                  rel="noreferrer"
                >
                  {questionnaireLink}
                </a>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={async () => {
                    await navigator.clipboard.writeText(questionnaireLink);
                    toast.success("Questionnaire link copied");
                  }}
                >
                  <Copy className="size-4 mr-2" />
                  Copy link
                </Button>
              </div>
            )}
            <div className="text-xs">
              This owner link expires after 48 hours. Send it to the store owner only.
            </div>
          </AlertDescription>
        </Alert>
      )}

      <div
        className="grid gap-3 rounded-lg border bg-white p-4 shadow-sm md:grid-cols-[1fr_280px]"
        data-testid="webstore-builder-header"
      >
        <div className="grid gap-3 md:grid-cols-4">
          <div>
            <div className="text-xs font-medium uppercase text-muted-foreground">
              Webstore Type
            </div>
            <div className="font-semibold capitalize">
              {formatLabel(
                store.webstore_type || store.store_type || "general",
              )}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium uppercase text-muted-foreground">
              Webstore Owner
            </div>
            <div className="font-semibold">
              {ownerAssignment?.name ||
                ownerAssignment?.email ||
                "Not assigned"}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium uppercase text-muted-foreground">
              Workflow status
            </div>
            <div className="font-semibold capitalize">
              {formatLabel(
                store.setup_state ||
                  setupProgress.data?.setup_state ||
                  store.status,
              )}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium uppercase text-muted-foreground">
              Last updated
            </div>
            <div className="font-semibold">
              {formatDateTime(store.updated_at || store.created_at)}
            </div>
          </div>
        </div>
        <div className="rounded-md border bg-slate-50 p-3">
          <div className="text-xs font-medium uppercase text-muted-foreground">
            Next required action
          </div>
          <div className="mt-1 text-sm font-medium">{nextRequiredAction}</div>
        </div>
      </div>
  </>;
}
