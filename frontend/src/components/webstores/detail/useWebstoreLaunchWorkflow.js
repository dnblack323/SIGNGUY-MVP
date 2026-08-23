import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { extractError } from "@/lib/api";
import {
  generateLaunchPacket,
  handoffWebstoreOrderToProduction,
  relaunchWebstore,
  requestWebstorePaymentProviderAction,
  sendLaunchPacket,
  setWebstoreStatus,
  updateWebstore,
  updateWebstoreChangeRequest,
} from "@/lib/webstores";
import { toast } from "sonner";

export function useWebstoreLaunchWorkflow({
  id,
  activePacket,
  store,
  readiness,
  refresh,
}) {
  const [promo, setPromo] = useState("");
  const [changeResponses, setChangeResponses] = useState({});

  const paymentNeedsAttention =
    store &&
    !store.checkout_enabled &&
    ["launch_ready", "owner_approved", "live"].includes(store.status)
      ? readiness.data?.payment_unavailable_reason ||
        store.checkout_unavailable_reason ||
        "Payment setup is incomplete."
      : "";

  const productionHandoff = useMutation({
    mutationFn: (orderId) => handoffWebstoreOrderToProduction(id, orderId),
    onSuccess: async (data) => {
      toast.success(
        data?.not_required
          ? "No production handoff is required"
          : "Order sent to production",
      );
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const saveGate = useMutation({
    mutationFn: (payload) => updateWebstore(id, payload),
    onSuccess: async () => {
      toast.success("Readiness updated");
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const packet = useMutation({
    mutationFn: () => generateLaunchPacket(id, { promotion_copy: promo }),
    onSuccess: async () => {
      toast.success("Launch packet generated");
      setPromo("");
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const sendPacket = useMutation({
    mutationFn: () => sendLaunchPacket(id, activePacket.id),
    onSuccess: async () => {
      toast.success("Launch packet sent");
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const launch = useMutation({
    mutationFn: () => setWebstoreStatus(id, "live"),
    onSuccess: async () => {
      toast.success("Webstore launched");
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const relaunch = useMutation({
    mutationFn: () => relaunchWebstore(id, "Staff requested Webstore relaunch"),
    onSuccess: async () => {
      toast.success("Relaunch gates passed; review and launch the Webstore");
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const paymentProviderAction = useMutation({
    mutationFn: (action) => requestWebstorePaymentProviderAction(id, action),
    onSuccess: async (result, action) => {
      const onboardingUrl = result?.result?.onboarding_url;
      if (
        onboardingUrl &&
        (action === "connect" || action === "resume_onboarding")
      ) {
        window.open(onboardingUrl, "_blank", "noopener,noreferrer");
      }
      toast.success(
        onboardingUrl
          ? "Stripe Connect setup opened"
          : "Stripe Connect status updated",
      );
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const updateChange = useMutation({
    mutationFn: ({ requestId, status, response }) =>
      updateWebstoreChangeRequest(id, requestId, { status, response }),
    onSuccess: async () => {
      toast.success("Change request updated");
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const markLaunchReady = useMutation({
    mutationFn: () =>
      setWebstoreStatus(
        id,
        "launch_ready",
        "All Stage 5 owner approval gates passed",
      ),
    onSuccess: async () => {
      toast.success("Marked ready to launch");
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  return {
    changeResponses,
    launch,
    markLaunchReady,
    packet,
    paymentNeedsAttention,
    paymentProviderAction,
    productionHandoff,
    promo,
    relaunch,
    saveGate,
    sendPacket,
    setChangeResponses,
    setPromo,
    updateChange,
  };
}
