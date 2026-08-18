import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { extractError } from "@/lib/api";
import {
  applyWebstoreAnswers,
  createWebstoreAssignment,
  previewWebstoreAnswerApplication,
  resendWebstoreInvitation,
  revokeWebstoreAssignment,
  reverseWebstoreAnswerApplication,
  sendWebstoreQuestionnaire,
  uploadWebstoreSetupFile,
} from "@/lib/webstores";
import { toast } from "sonner";
import { editableAnswerValue } from "./WebstoreDetailUtils";

export function useWebstoreSetupWorkflow({
  id,
  initialQuestionnaireDelivery,
  assignments,
  questionnaire,
  questionnaireResponse,
  refresh,
}) {
  const [questionnaireDelivery, setQuestionnaireDelivery] = useState(
    () => initialQuestionnaireDelivery || null,
  );
  const [assignment, setAssignment] = useState({
    role: "manager",
    email: "",
    name: "",
  });
  const [fileCategory, setFileCategory] = useState("logo");
  const [setupFile, setSetupFile] = useState(null);
  const [answerPreview, setAnswerPreview] = useState(null);
  const [selectedAnswerKeys, setSelectedAnswerKeys] = useState([]);
  const [proposedValues, setProposedValues] = useState({});
  const [lastApplication, setLastApplication] = useState(null);

  const ownerAssignment =
    (assignments.data || []).find((item) => item.role === "owner") ||
    (assignments.data || [])[0];
  const questionnaireSubmission = questionnaireResponse.data?.submission;
  const questionnaireAnswers = useMemo(
    () =>
      questionnaireSubmission?.submitted_snapshot?.answers ||
      questionnaireSubmission?.answers ||
      {},
    [questionnaireSubmission],
  );
  const questionnaireReviewTemplate = useMemo(
    () => ({
      sections: (questionnaire.data?.templates || []).flatMap(
        (template) => template.sections || [],
      ),
    }),
    [questionnaire.data],
  );
  const questionnaireReviewResponse = useMemo(
    () =>
      questionnaireSubmission
        ? {
            ...questionnaireSubmission,
            answers: questionnaireAnswers,
            submitted_snapshot: {
              ...(questionnaireSubmission.submitted_snapshot || {}),
              answers: questionnaireAnswers,
            },
          }
        : null,
    [questionnaireSubmission, questionnaireAnswers],
  );
  const questionnaireAnswerRows = Object.entries(questionnaireAnswers)
    .filter(
      ([, value]) => value !== undefined && value !== null && value !== "",
    )
    .slice(0, 8);

  const addAssignment = useMutation({
    mutationFn: () => createWebstoreAssignment(id, assignment),
    onSuccess: async (data) => {
      toast.success(
        data?.invitation?.status === "sent"
          ? "Invitation sent"
          : "Invitation link generated",
      );
      setAssignment({ role: "manager", email: "", name: "" });
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const uploadSetupFileMutation = useMutation({
    mutationFn: () => {
      const formData = new FormData();
      formData.append("category", fileCategory);
      formData.append("file", setupFile);
      return uploadWebstoreSetupFile(id, formData);
    },
    onSuccess: async () => {
      toast.success("Setup file uploaded");
      setSetupFile(null);
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const resendInvitation = useMutation({
    mutationFn: (assignmentId) => resendWebstoreInvitation(id, assignmentId),
    onSuccess: async () => {
      toast.success("Invitation regenerated");
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const sendQuestionnaire = useMutation({
    mutationFn: () => sendWebstoreQuestionnaire(id),
    onSuccess: async (data) => {
      setQuestionnaireDelivery(data);
      if (data?.email_sent) {
        toast.success("Questionnaire sent");
      } else {
        toast.error(
          `Questionnaire email was not sent (${data?.delivery_error || "delivery unavailable"}). Use the link shown below.`,
        );
      }
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const revokeAssignment = useMutation({
    mutationFn: (assignmentId) =>
      revokeWebstoreAssignment(id, assignmentId, "Revoked during setup review"),
    onSuccess: async () => {
      toast.success("Assignment revoked");
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const previewAnswers = useMutation({
    mutationFn: () =>
      previewWebstoreAnswerApplication(id, {
        submission_id: questionnaireResponse.data?.submission?.id,
        selected_answer_keys: selectedAnswerKeys,
        proposed_values: proposedValues,
      }),
    onSuccess: (data) => setAnswerPreview(data),
    onError: (err) => toast.error(extractError(err)),
  });

  const applyAnswers = useMutation({
    mutationFn: () =>
      applyWebstoreAnswers(id, {
        submission_id: questionnaireResponse.data?.submission?.id,
        selected_answer_keys: selectedAnswerKeys,
        proposed_values: proposedValues,
        reason: "Apply verified Webstore intake answers",
        idempotency_key: `apply-${questionnaireResponse.data?.submission?.id}-${[...selectedAnswerKeys].sort().join("-")}`,
      }),
    onSuccess: async (data) => {
      toast.success("Answers applied");
      setLastApplication(data?.application || null);
      setAnswerPreview(null);
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const reverseAnswers = useMutation({
    mutationFn: () =>
      reverseWebstoreAnswerApplication(id, lastApplication.id, {
        reason: "Reverse setup answer application",
        idempotency_key: `reverse-${lastApplication.id}`,
      }),
    onSuccess: async () => {
      toast.success("Answer application reversed");
      setLastApplication(null);
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  return {
    addAssignment,
    answerPreview,
    applyAnswers,
    assignment,
    editableAnswerValue,
    fileCategory,
    lastApplication,
    ownerAssignment,
    previewAnswers,
    proposedValues,
    questionnaireAnswerRows,
    questionnaireAnswers,
    questionnaireDelivery,
    questionnaireReviewResponse,
    questionnaireReviewTemplate,
    questionnaireSubmission,
    resendInvitation,
    reverseAnswers,
    revokeAssignment,
    selectedAnswerKeys,
    sendQuestionnaire,
    setAnswerPreview,
    setAssignment,
    setFileCategory,
    setProposedValues,
    setQuestionnaireDelivery,
    setSelectedAnswerKeys,
    setSetupFile,
    setupFile,
    uploadSetupFileMutation,
  };
}
