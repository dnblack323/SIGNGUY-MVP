import { CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function GuidedSetupModule({
  store,
  questionnaireSubmission,
  activeProducts,
  activePacket,
  setupFiles,
  branding,
  readiness,
  onShowTab,
  onSendQuestionnaire,
  onGeneratePacket,
  onSendPacket,
  onLaunch,
  sendingQuestionnaire,
  generatingPacket,
  sendingPacket,
  launching,
}) {
  const setupState = store.setup_state || store.status || "not_started";
  const questionnaireSent = [
    "questionnaire_sent",
    "waiting_on_store_owner",
    "questionnaire_submitted",
    "staff_review",
    "setup_in_progress",
    "setup_complete",
  ].includes(setupState) || store.status === "questionnaire_sent";
  const questionnaireSubmitted = Boolean(questionnaireSubmission);
  const questionnaireReviewed = ["reviewed", "approved"].includes(questionnaireSubmission?.status);
  const hasBranding = Boolean(
    branding?.draft ||
      branding?.published ||
      setupFiles.some((file) => ["logo", "banner"].includes(file.category)),
  );
  const hasProducts = activeProducts.length > 0;
  const packetSent = Boolean(
    activePacket?.sent_at ||
      activePacket?.delivered_at ||
      ["sent", "delivered", "sent_for_approval"].includes(activePacket?.status) ||
      ["sent", "delivered"].includes(activePacket?.delivery_status),
  );
  const ownerApproved = Boolean(
    store.owner_approved_at ||
      ["owner_approved", "launch_ready", "live"].includes(store.status),
  );

  const steps = [
    {
      key: "basics",
      title: "Store basics",
      description: "The Webstore type, owner, dates, and short welcome message are recorded.",
      complete: Boolean(store.name && store.store_type),
    },
    {
      key: "questionnaire",
      title: "Owner questionnaire",
      description: questionnaireSubmitted
        ? "The owner sent answers back. Review them before applying anything."
        : questionnaireSent
          ? "The type-specific questionnaire is with the owner."
          : "Send the existing questionnaire for this Webstore type.",
      complete: questionnaireSubmitted,
      waiting: questionnaireSent && !questionnaireSubmitted,
    },
    {
      key: "answers",
      title: "Review answers",
      description: questionnaireReviewed
        ? "The reviewed answers are preserved and ready to guide setup."
        : questionnaireSubmitted
          ? "Preview proposed changes, then explicitly apply only what belongs in setup."
          : "This opens after the owner submits the questionnaire.",
      complete: questionnaireReviewed,
      locked: !questionnaireSubmitted,
    },
    {
      key: "build",
      title: "Build products and Storefront",
      description: hasProducts && hasBranding
        ? "Products and draft branding are ready for the launch packet."
        : "Use the answers to create product drafts, add mockups, and confirm the draft branding.",
      complete: hasProducts && hasBranding,
      locked: !questionnaireReviewed,
    },
    {
      key: "packet",
      title: "Send launch packet",
      description: activePacket
        ? packetSent
          ? "The packet is with the owner for review."
          : "The packet is ready to send to the owner."
        : "Create the packet from the current products and draft Storefront.",
      complete: packetSent,
      locked: !hasProducts || !hasBranding,
    },
    {
      key: "launch",
      title: "Owner approval and launch",
      description: store.status === "live"
        ? "The Webstore is live."
        : ownerApproved
          ? readiness?.ready
            ? "Owner approval is recorded and the Webstore can be launched."
            : readiness?.payment_unavailable_reason || "Owner approval is recorded; remaining launch gates are shown in Review & Launch."
          : "The owner must approve the packet before launch.",
      complete: store.status === "live",
      locked: !packetSent,
    },
  ];
  const actionableIndex = steps.findIndex((step) => !step.complete && !step.waiting && !step.locked);
  const currentIndex = actionableIndex >= 0 ? actionableIndex : steps.findIndex((step) => step.waiting);

  const actionFor = (step) => {
    if (step.complete || step.waiting || step.locked) return null;
    if (step.key === "questionnaire") {
      return <Button size="sm" onClick={onSendQuestionnaire} disabled={sendingQuestionnaire} data-testid="guided-send-questionnaire">{sendingQuestionnaire ? "Sending..." : "Send Questionnaire"}</Button>;
    }
    if (step.key === "answers") {
      return <Button size="sm" onClick={() => onShowTab("review-launch")} data-testid="guided-review-answers">Review Answers</Button>;
    }
    if (step.key === "build") {
      return <Button size="sm" onClick={() => onShowTab(hasProducts ? "storefront" : "products")} data-testid="guided-build-products">{hasProducts ? "Open Storefront" : "Build Products"}</Button>;
    }
    if (step.key === "packet") {
      if (!activePacket) return <Button size="sm" onClick={onGeneratePacket} disabled={generatingPacket} data-testid="guided-generate-packet">{generatingPacket ? "Creating..." : "Create Launch Packet"}</Button>;
      return <Button size="sm" onClick={onSendPacket} disabled={sendingPacket} data-testid="guided-send-packet">{sendingPacket ? "Sending..." : "Send Launch Packet"}</Button>;
    }
    if (step.key === "launch") {
      if (!ownerApproved || !readiness?.ready) return <Button size="sm" variant="outline" onClick={() => onShowTab("review-launch")} data-testid="guided-open-launch-gates">Open Launch Gates</Button>;
      return <Button size="sm" onClick={onLaunch} disabled={launching} data-testid="guided-launch-webstore">{launching ? "Launching..." : "Launch Webstore"}</Button>;
    }
    return null;
  };

  return (
    <Card className="border-sky-200 bg-sky-50/40" data-testid="webstore-guided-setup-module">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">Webstore Setup</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">Follow the next step. The shop handles the setup; the owner only supplies the choices and answers requested.</p>
          </div>
          <Badge variant="outline">{steps.filter((step) => step.complete).length}/{steps.length} complete</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-1">
        <div data-testid="webstore-setup-checklist">
        {steps.map((step, index) => {
          const isCurrent = index === currentIndex;
          return (
            <div key={step.key} className="relative flex gap-3" data-testid={`guided-setup-step-${step.key}`}>
              {index < steps.length - 1 && <div className="absolute left-3 top-7 bottom-0 w-px bg-sky-200" />}
              <div className={`z-10 mt-1 flex size-6 shrink-0 items-center justify-center rounded-full border text-xs ${step.complete ? "border-emerald-600 bg-emerald-100 text-emerald-700" : step.waiting ? "border-amber-500 bg-amber-100 text-amber-700" : isCurrent ? "border-sky-700 bg-sky-700 text-white" : "border-slate-300 bg-white text-slate-500"}`}>
                {step.complete ? <CheckCircle2 className="size-4" /> : index + 1}
              </div>
              <div className={`min-w-0 flex-1 pb-4 ${step.locked ? "opacity-60" : ""}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="font-medium">{step.title}</div>
                  {actionFor(step)}
                </div>
                <div className="mt-1 text-sm text-muted-foreground">{step.description}</div>
                {step.waiting && <div className="mt-1 text-xs font-medium text-amber-800">Waiting on owner</div>}
              </div>
            </div>
          );
        })}
        </div>
        <div className="pt-2 text-xs text-muted-foreground">Advanced Setup remains available for staff-only controls. Nothing is published automatically by this module.</div>
      </CardContent>
    </Card>
  );
}
