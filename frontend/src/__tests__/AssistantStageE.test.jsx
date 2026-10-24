import React from "react";
import { MemoryRouter } from "react-router-dom";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";
import ActionProposal from "@/components/assistant/ActionProposal";
import MemoryManager from "@/components/assistant/MemoryManager";
import SavedActionRecord from "@/components/assistant/SavedActionRecord";
import * as api from "@/lib/businessAssistant";

jest.mock("@/lib/businessAssistant", () => ({ editAssistantProposal: jest.fn(), confirmAssistantProposal: jest.fn(), cancelAssistantProposal: jest.fn(), executeAssistantProposal: jest.fn(), saveAssistantMemory: jest.fn(), editAssistantMemory: jest.fn(), deleteAssistantMemory: jest.fn(), getAssistantSavedRecord: jest.fn() }));
const p = { id: "p1", action_type: "internal_note", title: "Customer note", summary: "Preview only", revision: 1, status: "proposed", editable_payload: { title: "Customer note", body: "Exact note" }, target_refs: [{ type: "customer", id: "c1", label: "Smith Construction", route: "/customers/c1" }] };
beforeEach(() => { jest.resetAllMocks(); });

test("conversational suggestion loads the existing topic for an explicitly approved correction", async () => {
  const item = { id: "m1", memory_key: "updates", content_text: "Concise", updated_at: "v1" };
  renderWithProviders(<MemoryManager items={[item]} context={{}} suggestion={{ memory_key: "updates", content_text: "Detailed" }} onChanged={jest.fn()} />);
  expect(screen.getByLabelText("Memory content")).toHaveValue("Detailed");
  expect(screen.getByText("Save memory correction")).toBeDisabled();
  expect(api.editAssistantMemory).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("checkbox")); fireEvent.click(screen.getByText("Save memory correction"));
  await waitFor(() => expect(api.editAssistantMemory).toHaveBeenCalledWith("m1", { memory_key: "updates", content_text: "Detailed", expected_updated_at: "v1" }));
});

test("preview edits invalidate confirmation and execution receipt keeps proposal identity", async () => {
  const onUpdated = jest.fn();
  const { rerender } = renderWithProviders(<ActionProposal proposal={p} onUpdated={onUpdated} />);
  expect(screen.getByText(/Destination:/)).toHaveTextContent("Smith Construction");
  expect(api.executeAssistantProposal).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Action content"), { target: { value: "Corrected exact note" } });
  expect(screen.getByText("Confirm this preview")).toBeDisabled();
  const edited = { ...p, revision: 2, status: "edited", editable_payload: { ...p.editable_payload, body: "Corrected exact note" } };
  api.editAssistantProposal.mockResolvedValue(edited);
  fireEvent.click(screen.getByText("Save preview changes"));
  await waitFor(() => expect(onUpdated).toHaveBeenCalledWith(edited));
  rerender(<MemoryRouter><ActionProposal proposal={edited} onUpdated={onUpdated} /></MemoryRouter>);
  api.confirmAssistantProposal.mockResolvedValue({ ...edited, status: "confirmed" });
  fireEvent.click(screen.getByText("Confirm this preview"));
  await waitFor(() => expect(api.confirmAssistantProposal).toHaveBeenCalledWith("p1", 2));
  expect(api.executeAssistantProposal).not.toHaveBeenCalled();
  rerender(<MemoryRouter><ActionProposal proposal={{ ...edited, status: "confirmed" }} onUpdated={onUpdated} /></MemoryRouter>);
  api.executeAssistantProposal.mockResolvedValue({ id: "execution-id", proposal_id: "p1", status: "succeeded", canonical_result: { note_id: "n1", route: "/studio/assistant?record_proposal=p1", assistant_summary: "Actual note created" } });
  fireEvent.click(screen.getByText("Create confirmed record")); fireEvent.click(screen.getByText("Create confirmed record"));
  await waitFor(() => expect(onUpdated).toHaveBeenLastCalledWith(expect.objectContaining({ id: "p1", status: "succeeded", result: expect.objectContaining({ note_id: "n1" }) })));
  expect(api.executeAssistantProposal).toHaveBeenCalledTimes(1);
});

test("explicit approval is required for memory creation and corrections", async () => {
  const onChanged = jest.fn(); const item = { id: "m1", memory_key: "updates", content_text: "Concise", updated_at: "version1" };
  renderWithProviders(<MemoryManager items={[item]} context={{}} onChanged={onChanged} />);
  fireEvent.change(screen.getByLabelText("Memory topic"), { target: { value: "format" } });
  fireEvent.change(screen.getByLabelText("Memory content"), { target: { value: "Short updates" } });
  expect(screen.getByText("Approve and save memory")).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByText("Approve and save memory"));
  await waitFor(() => expect(api.saveAssistantMemory).toHaveBeenCalledWith({ memory_key: "format", content_text: "Short updates" }));
  fireEvent.click(screen.getByText("Edit memory"));
  expect(screen.getByText("Save memory correction")).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Memory content"), { target: { value: "Detailed" } });
  fireEvent.click(screen.getByRole("checkbox")); fireEvent.click(screen.getByText("Save memory correction"));
  await waitFor(() => expect(api.editAssistantMemory).toHaveBeenCalledWith("m1", { memory_key: "updates", content_text: "Detailed", expected_updated_at: "version1" }));
  fireEvent.click(screen.getByText("Delete memory"));
  await waitFor(() => expect(api.deleteAssistantMemory).toHaveBeenCalledWith("m1"));
});

test("saved record link loads actual canonical content and denies unavailable records", async () => {
  api.getAssistantSavedRecord.mockResolvedValue({ id: "draft1", kind: "email_draft", title: "Follow-up", content: "Professional draft", sent: false, destinations: [] });
  const { rerender } = renderWithProviders(<SavedActionRecord identity="u1" proposalId="p1" />);
  expect(await screen.findByText("Professional draft")).toBeInTheDocument();
  expect(screen.getByText("Draft saved. No email was sent.")).toBeInTheDocument();
  api.getAssistantSavedRecord.mockRejectedValue(new Error("Access denied"));
  rerender(<SavedActionRecord identity="u2" proposalId="p1" />);
  expect(screen.queryByText("Professional draft")).not.toBeInTheDocument();
  expect(await screen.findByRole("alert")).toBeInTheDocument();
});
