import { Link } from "react-router-dom";
import { ExternalLink, Eye, Mail, RotateCcw } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { primaryActionFor } from "./WebstoreNextAction";

export default function WebstoreDetailHeader({ model }) {
  const { formatLabel, id, ownerAssignment, relaunch, setPacketOpen, stage, store } = model;
  const primary = primaryActionFor(model);

  return (
    <PageHeader
      title={store.name}
      subtitle={`Webstores setup - ${formatLabel(store.webstore_type || store.store_type || "general")} - ${stage?.staff_label || ""}`}
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
          <Button variant="outline" size="sm" onClick={() => setPacketOpen(true)} data-testid="webstore-information-packet">
            <Mail className="size-4 mr-2" />
            Information Packet
          </Button>
          {stage?.key === "closed" && (
            <Button variant="outline" size="sm" disabled={relaunch.isPending} onClick={() => relaunch.mutate()} data-testid="webstore-relaunch">
              <RotateCcw className="size-4 mr-2" />
              {relaunch.isPending ? "Checking..." : "Prepare Relaunch"}
            </Button>
          )}
          {stage?.key === "live" && (store.public_url || store.public_slug || store.slug) ? (
            <Button asChild variant="outline" size="sm">
              <Link to={store.public_url || `/p/webstores/${store.public_slug || store.slug}`}>
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
          {primary && (
            <Button
              size="sm"
              variant={primary.variant || "default"}
              disabled={primary.disabled}
              onClick={primary.onClick}
              data-testid="webstore-primary-action"
            >
              {primary.label}
            </Button>
          )}
        </div>
      }
    />
  );
}
