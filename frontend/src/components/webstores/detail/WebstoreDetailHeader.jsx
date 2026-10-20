import { Link } from "react-router-dom";
import { ExternalLink, Eye, Mail, RotateCcw } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { webstoreStatusLabel } from "./WebstoreDetailUtils";

export default function WebstoreDetailHeader({ model }) {
  const {
    formatDateTime,
    formatLabel,
    id,
    nextRequiredAction,
    ownerAssignment,
    questionnaire,
    relaunch,
    setPacketOpen,
    setupProgress,
    store,
  } = model;

return <>
      <PageHeader
        title={store.name}
        subtitle={`Webstores setup - ${formatLabel(store.webstore_type || store.store_type || "general")} - ${webstoreStatusLabel(store.status)}`}
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
              onClick={() => setPacketOpen(true)}
              data-testid="webstore-information-packet"
            >
              <Mail className="size-4 mr-2" />
              Information Packet
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
