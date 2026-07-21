# EC19 Placeholder Registry

EC19 exposes the approved placeholder registry during onboarding, but the canonical placeholder engine remains the EC10/EC12 template service.

## Runtime Contract

- `GET /api/onboarding/placeholders` returns approved placeholder keys grouped for onboarding UI.
- `POST /api/onboarding/placeholders/preview` renders raw text with provided context.
- Unknown placeholders are rejected.
- Missing values are returned as `missing_placeholders`.
- Template exercises call `template_service.validate_template_payload` and `template_service.render_channels`.

## Implemented Placeholders

EC19 uses the current `template_service.VALID_PLACEHOLDERS` set, including customer, employee, order, work-order, appointment, task, support, feature, bug, shop, and contact fields.

## AI Credit Boundary

Placeholder preview, template validation, and saved reusable templates do not consume AI credits. EC19 does not call EC16 metering for these non-AI operations.

## Remaining Follow-Up

Broader Document Library/DocuLink placeholder expansion for Quote, Invoice, Webstore, and Wrap Lab document-specific fields remains with its owning document checkpoint unless already covered by the canonical template engine.
