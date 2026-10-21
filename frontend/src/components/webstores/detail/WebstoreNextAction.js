// Staff workspace tabs (Phase 3, D3-4). Keys match the backend next action's `tab`.
export const STAFF_TABS = [
  { value: "overview", label: "Overview" },
  { value: "setup", label: "Setup" },
  { value: "products", label: "Products" },
  { value: "storefront", label: "Storefront" },
  { value: "review-launch", label: "Approval & Launch" },
  { value: "orders", label: "Orders & Production" },
  { value: "activity", label: "Messages & Activity" },
];

export function staffTabLabel(value) {
  return STAFF_TABS.find((tab) => tab.value === value)?.label || "Overview";
}

/**
 * The header's one primary button for the backend next action. The frontend
 * only maps an action key to the existing control; it never decides the step.
 */
export function primaryActionFor(model) {
  const { activeTab, nextAction, launch, packet, sendPacket, setActiveTab, setPacketOpen, setReviewOpen } = model;
  if (!nextAction || nextAction.key === "none") return null;
  const target = nextAction.tab || "overview";
  // A button that opens the tab already on screen does nothing useful.
  const openTab = target === activeTab ? null : { label: `Open ${staffTabLabel(target)}`, onClick: () => setActiveTab(target) };
  if (nextAction.actor !== "shop") return openTab && { ...openTab, variant: "outline" };
  switch (nextAction.key) {
    case "send_information_packet":
      return { label: "Send Information Packet", onClick: () => setPacketOpen(true) };
    case "review_questionnaire":
      return { label: "Review Answers", onClick: () => setReviewOpen(true) };
    case "packet_generated":
      return { label: packet.isPending ? "Creating..." : "Create Launch Packet", onClick: () => packet.mutate(), disabled: packet.isPending };
    case "packet_delivered":
      return { label: sendPacket.isPending ? "Sending..." : "Send Launch Packet", onClick: () => sendPacket.mutate(), disabled: sendPacket.isPending };
    case "publish":
      return { label: launch.isPending ? "Publishing..." : "Publish Webstore", onClick: () => launch.mutate(), disabled: launch.isPending };
    default:
      return openTab;
  }
}
