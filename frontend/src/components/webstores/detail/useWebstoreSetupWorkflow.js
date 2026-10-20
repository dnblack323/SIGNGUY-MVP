import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { extractError } from "@/lib/api";
import {
  createWebstoreAssignment,
  resendWebstoreInvitation,
  revokeWebstoreAssignment,
  uploadWebstoreSetupFile,
} from "@/lib/webstores";
import { toast } from "sonner";

export function useWebstoreSetupWorkflow({
  id,
  assignments,
  questionnaireResponse,
  refresh,
}) {
  const [packetOpen, setPacketOpen] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [assignment, setAssignment] = useState({
    role: "manager",
    email: "",
    name: "",
  });
  const [fileCategory, setFileCategory] = useState("logo");
  const [setupFile, setSetupFile] = useState(null);

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

  const revokeAssignment = useMutation({
    mutationFn: (assignmentId) =>
      revokeWebstoreAssignment(id, assignmentId, "Revoked during setup review"),
    onSuccess: async () => {
      toast.success("Assignment revoked");
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  return {
    packetOpen,
    reviewOpen,
    setPacketOpen,
    setReviewOpen,
    addAssignment,
    assignment,
    fileCategory,
    ownerAssignment,
    questionnaireAnswerRows,
    questionnaireAnswers,
    questionnaireSubmission,
    resendInvitation,
    revokeAssignment,
    setAssignment,
    setFileCategory,
    setSetupFile,
    setupFile,
    uploadSetupFileMutation,
  };
}
