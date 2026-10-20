import { useEffect, useRef, useState } from "react";
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
  const [answers, setAnswersState] = useState({});
  const [saveState, setSaveState] = useState("idle");
  const [submitting, setSubmitting] = useState(false);
  const dirty = useRef(false);
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
        dirty.current = false;
        setAnswersState(
          q.data.submission?.answers ||
            q.data.submission?.submitted_snapshot?.answers ||
            {},
        );
      })
      .catch((e) => setErr(portalExtractError(e)));
  }

  useEffect(load, [webstoreId]);

  function setAnswers(next) {
    dirty.current = true;
    setSaveState("unsaved");
    setAnswersState(next);
  }

  async function persistDraft(current) {
    setSaveState("saving");
    try {
      await portalApi.post(`/portal/webstores/${webstoreId}/questionnaire/draft`, { answers: current, known_products: [] });
      dirty.current = false;
      setSaveState("saved");
      return true;
    } catch (e) {
      setSaveState("error");
      return false;
    }
  }

  // Autosave: a quiet draft save shortly after the owner stops typing (never reloads the form).
  useEffect(() => {
    if (!dirty.current || submitting) return undefined;
    const timer = setTimeout(() => persistDraft(answers), 1200);
    return () => clearTimeout(timer);
  }, [answers]); // eslint-disable-line react-hooks/exhaustive-deps

  async function saveDraft() {
    if (await persistDraft(answers)) toast.success("Draft saved");
    else toast.error("Draft was not saved. Check your connection and try again.");
  }

  async function uploadQuestionFile(question, file) {
    const formData = new FormData();
    formData.append("category", question.key);
    formData.append("file", file);
    try {
      const r = await portalApi.post(`/portal/webstores/${webstoreId}/setup-files`, formData, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("File uploaded");
      return { file_id: r.data.file.id, file_name: r.data.file.file_name, field_key: question.key };
    } catch (e) {
      toast.error(portalExtractError(e));
      return null;
    }
  }

  async function submitQuestionnaire() {
    if (submitting) return;
    setSubmitting(true);
    try {
      await portalApi.post(`/portal/webstores/${webstoreId}/questionnaire`, {
        answers,
        known_products: [],
      });
      dirty.current = false;
      toast.success("Questionnaire submitted");
      load();
    } catch (e) {
      toast.error(portalExtractError(e));
    } finally {
      setSubmitting(false);
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
    saveState,
    submitting,
    submitQuestionnaire,
    uploadQuestionFile,
    uploadSetupFile,
    approve,
    rejectPacket,
    requestChanges,
    acceptTerms,
    decideProduct,
    decideMockup,
  };
}
