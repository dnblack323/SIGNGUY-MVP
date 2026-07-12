# Signed-PDF Composite Rendering — Boundary Decision

**Status:** DEFERRED to a specifically named later checkpoint. **Not part of EC6 exit conditions.**
**Recorded:** 2026-02, at EC6 close-out.

## What ships in EC6
- The **permanent Signature and Signature Request records are complete** — `signature_requests`, `signatures`, `required_signers` with per-signer status, `SignatureRequestStatus` lifecycle (draft → sent → partially_signed → completed / cancelled), signer IP + user_agent + token_id captured on each `Signature` row.
- **Signature evidence is immutable** — each `Signature` is inserted once and never edited. Completion timestamp, signer name, signer email, typed text or drawn signature file reference are all preserved verbatim.
- **`signed_pdf_file_id` field is reserved** on the `SignatureRequest` model but is intentionally left empty in EC6. This field will be populated by a future PDF-composite service in a later named checkpoint.
- **The absence of a stamped composite PDF does NOT affect signature validity inside the current product model.** Signature evidence is the row in `signatures` + the request status. The composite PDF is a courtesy artifact for downstream distribution, not the primary evidence.
- **No UI claims that a signed composite PDF exists.** The Signature Request views in the staff and portal surfaces display the request status + per-signer status only; there is no "Download signed PDF" affordance in EC6. If added later it will be gated on `signed_pdf_file_id` being non-null.

## Master plan review
Per a full text search across `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md`, the phrase "signed pdf" / "signed-PDF" / `signed_pdf` **does not appear**. §11.2 (Signatures) requires immutable signature evidence + audit — which EC6 delivers. Composite PDF rendering is not enumerated as an EC6 exit condition in §30A.7.

## Where composite rendering will land
The future checkpoint is **"EC6.2 — Signed PDF Composite Rendering"** and will:
- Live behind the existing shared file/document services (no new storage system).
- Consume `signature_requests` + `signatures` at completion time (webhook or scheduled task).
- Generate one composite PDF per completed request, store it via the existing storage service, and set `signature_requests.signed_pdf_file_id` + `signed_pdf_document_id` atomically.
- Expose an authenticated download endpoint gated by `document:read` (staff) or the signer's portal identity (customer).
- Emit an audit event `signature_request.composite_generated`.

EC6.2 is separate from EC7 (Inventory / Purchasing / Finance / Reporting) and does not block it. It will be scheduled after EC6 is fully closed and EC7 preflight is approved.

## Explicit non-implications
- Signatures collected during EC6 will be composited retroactively when EC6.2 lands.
- No data migration is required; the model already reserves the field.
- No API contract change is required for existing callers; `signed_pdf_file_id` is optional today.

## Files affected in EC6
- `backend/app/models/signature.py::SignatureRequest.signed_pdf_file_id` — declared, always `None` in EC6.
- `backend/app/services/approvals_signatures_service.py::record_signature` — sets `SignatureRequestStatus="completed"` when all required signers have signed; does NOT invoke a composite renderer.
- `backend/app/routers/signatures.py::get_request` — returns the reserved field for API stability but never populates it.
- Frontend — no "Download signed PDF" button anywhere.

## Owner acknowledgement item recorded in EC6 evidence
`/app/evidence/EC6_evidence.md` — "Signed-PDF boundary" section records this decision + points at this document.
