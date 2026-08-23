import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import portalApi, { portalExtractError } from "@/portal/portalApi";
import { toast } from "sonner";

export function useWebstoreOwnerPortal() {
  const { webstoreId } = useParams();
  const [data, setData] = useState(null);
  const [questionnaire, setQuestionnaire] = useState(null);
  const [progress, setProgress] = useState(null);
  const [files, setFiles] = useState([]);
  const [err, setErr] = useState(null);
  const [answers, setAnswers] = useState({});
  const [fileCategory, setFileCategory] = useState("logo");
  const [setupFile, setSetupFile] = useState(null);
  const [changeRequest, setChangeRequest] = useState({
    category: "general",
    comment: "",
  });
  const [packetComment, setPacketComment] = useState("");
  const [productComments, setProductComments] = useState({});

  function load() {
    Promise.all([
      portalApi.get(`/portal/webstores/${webstoreId}`),
      portalApi.get(`/portal/webstores/${webstoreId}/questionnaire`),
      portalApi.get(`/portal/webstores/${webstoreId}/setup-progress`),
      portalApi.get(`/portal/webstores/${webstoreId}/setup-files`),
    ])
      .then(([detail, q, setup, fileList]) => {
        setData(detail.data);
        setQuestionnaire(q.data);
        setProgress(setup.data);
        setFiles(fileList.data.items || []);
        setAnswers(
          q.data.submission?.answers ||
            q.data.submission?.submitted_snapshot?.answers ||
            {},
        );
      })
      .catch((e) => setErr(portalExtractError(e)));
  }

  useEffect(load, [webstoreId]);

  async function saveDraft() {
    try {
      await portalApi.post(
        `/portal/webstores/${webstoreId}/questionnaire/draft`,
        { answers, known_products: [] },
      );
      toast.success("Draft saved");
      load();
    } catch (e) {
      toast.error(portalExtractError(e));
    }
  }

  async function submitQuestionnaire() {
    try {
      await portalApi.post(`/portal/webstores/${webstoreId}/questionnaire`, {
        answers,
        known_products: [],
      });
      toast.success("Questionnaire submitted");
      load();
    } catch (e) {
      toast.error(portalExtractError(e));
    }
  }

  async function uploadSetupFile() {
    if (!setupFile) return;
    try {
      const formData = new FormData();
      formData.append("category", fileCategory);
      formData.append("file", setupFile);
      await portalApi.post(
        `/portal/webstores/${webstoreId}/setup-files`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      toast.success("File uploaded");
      setSetupFile(null);
      load();
    } catch (e) {
      toast.error(portalExtractError(e));
    }
  }

  async function approve() {
    try {
      await portalApi.post(
        `/portal/webstores/${webstoreId}/launch-packets/${data.launch_packet.id}/approve`,
        { comment: packetComment },
      );
      toast.success("Launch approved");
      setPacketComment("");
      load();
    } catch (e) {
      toast.error(portalExtractError(e));
    }
  }

  async function rejectPacket() {
    if (!packetComment.trim()) return;
    try {
      await portalApi.post(
        `/portal/webstores/${webstoreId}/launch-packets/${data.launch_packet.id}/reject`,
        { comment: packetComment },
      );
      toast.success("Launch packet rejected");
      setPacketComment("");
      load();
    } catch (e) {
      toast.error(portalExtractError(e));
    }
  }

  async function requestChanges() {
    if (!changeRequest.comment.trim()) return;
    try {
      await portalApi.post(
        `/portal/webstores/${webstoreId}/launch-packets/${data.launch_packet.id}/request-changes`,
        changeRequest,
      );
      toast.success("Change request sent");
      setChangeRequest({ category: "general", comment: "" });
      load();
    } catch (e) {
      toast.error(portalExtractError(e));
    }
  }

  async function acceptTerms() {
    try {
      await portalApi.post(`/portal/webstores/${webstoreId}/terms/accept`, {
        terms_version: data.current_terms_version,
      });
      toast.success("Terms accepted");
      load();
    } catch (e) {
      toast.error(portalExtractError(e));
    }
  }

  async function decideProduct(productId, decision) {
    const comment = productComments[productId] || "";
    if (decision !== "approve" && !comment.trim()) return;
    try {
      await portalApi.post(
        `/portal/webstores/${webstoreId}/products/${productId}/approval`,
        { decision, comment },
      );
      toast.success("Product decision saved");
      setProductComments({ ...productComments, [productId]: "" });
      load();
    } catch (e) {
      toast.error(portalExtractError(e));
    }
  }

  async function decideMockup(mockupId, decision, productId) {
    const comment = productComments[productId] || "";
    if (decision !== "approve" && !comment.trim()) return;
    try {
      await portalApi.post(
        `/portal/webstores/${webstoreId}/mockups/${mockupId}/approval`,
        { decision, comment },
      );
      toast.success("Mockup decision saved");
      load();
    } catch (e) {
      toast.error(portalExtractError(e));
    }
  }

  return {
    webstoreId,
    data,
    questionnaire,
    progress,
    files,
    err,
    answers,
    setAnswers,
    fileCategory,
    setFileCategory,
    setupFile,
    setSetupFile,
    changeRequest,
    setChangeRequest,
    packetComment,
    setPacketComment,
    productComments,
    setProductComments,
    saveDraft,
    submitQuestionnaire,
    uploadSetupFile,
    approve,
    rejectPacket,
    requestChanges,
    acceptTerms,
    decideProduct,
    decideMockup,
  };
}
