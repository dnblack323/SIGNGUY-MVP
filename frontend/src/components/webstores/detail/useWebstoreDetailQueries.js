import { useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getLaunchReadiness,
  getWebstore,
  getWebstoreOrders,
  getWebstorePaymentProviderStatus,
  getWebstoreQuestionnaire,
  getWebstoreQuestionnaireResponse,
  getWebstoreReports,
  getWebstoreSetupProgress,
  listProductTemplates,
  listWebstoreActivity,
  listWebstoreAssignments,
  listWebstoreProductCategories,
  listWebstoreSetupFiles,
} from "@/lib/webstores";

export function useWebstoreDetailQueries(id) {
  const qc = useQueryClient();
  const detail = useQuery({
    queryKey: ["webstore", id],
    queryFn: () => getWebstore(id),
    enabled: !!id,
  });
  const templates = useQuery({
    queryKey: ["webstore-product-templates"],
    queryFn: listProductTemplates,
  });
  const categories = useQuery({
    queryKey: ["webstore-product-categories", id],
    queryFn: () => listWebstoreProductCategories(id),
    enabled: !!id,
  });
  const readiness = useQuery({
    queryKey: ["webstore-readiness", id],
    queryFn: () => getLaunchReadiness(id),
    enabled: !!id,
  });
  const paymentProvider = useQuery({
    queryKey: ["webstore-payment-provider", id],
    queryFn: () => getWebstorePaymentProviderStatus(id),
    enabled: !!id,
  });
  const reports = useQuery({
    queryKey: ["webstore-reports", id],
    queryFn: () => getWebstoreReports(id),
    enabled: !!id,
  });
  const orders = useQuery({
    queryKey: ["webstore-orders", id],
    queryFn: () => getWebstoreOrders(id, { limit: 20 }),
    enabled: !!id,
  });
  const activity = useQuery({
    queryKey: ["webstore-activity", id],
    queryFn: () => listWebstoreActivity(id, { limit: 20 }),
    enabled: !!id,
  });
  const setupProgress = useQuery({
    queryKey: ["webstore-setup-progress", id],
    queryFn: () => getWebstoreSetupProgress(id),
    enabled: !!id,
  });
  const assignments = useQuery({
    queryKey: ["webstore-assignments", id],
    queryFn: () => listWebstoreAssignments(id),
    enabled: !!id,
  });
  const questionnaire = useQuery({
    queryKey: ["webstore-questionnaire", id],
    queryFn: () => getWebstoreQuestionnaire(id),
    enabled: !!id,
  });
  const questionnaireResponse = useQuery({
    queryKey: ["webstore-questionnaire-response", id],
    queryFn: () => getWebstoreQuestionnaireResponse(id),
    enabled: !!id,
  });
  const setupFiles = useQuery({
    queryKey: ["webstore-setup-files", id],
    queryFn: () => listWebstoreSetupFiles(id),
    enabled: !!id,
  });

  const store = detail.data?.webstore;
  const setupFileItems = setupFiles.data?.items || setupFiles.data || [];
  const activePacket = useMemo(
    () => (detail.data?.launch_packets || [])[0],
    [detail.data],
  );

  const refresh = async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["webstore", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-readiness", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-payment-provider", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-reports", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-orders", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-activity", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-setup-progress", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-assignments", id] }),
      qc.invalidateQueries({
        queryKey: ["webstore-questionnaire-response", id],
      }),
      qc.invalidateQueries({ queryKey: ["webstore-setup-files", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-product-categories", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-product-templates"] }),
    ]);
  };

  return {
    qc,
    detail,
    templates,
    categories,
    readiness,
    paymentProvider,
    reports,
    orders,
    activity,
    setupProgress,
    assignments,
    questionnaire,
    questionnaireResponse,
    setupFiles,
    store,
    setupFileItems,
    activePacket,
    refresh,
  };
}
