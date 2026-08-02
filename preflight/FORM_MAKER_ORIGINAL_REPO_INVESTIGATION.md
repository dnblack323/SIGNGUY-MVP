# Form Maker Original Repo Investigation

Status: investigation only. No implementation in this pass.

User decision: the product/module name is `Webstores`. Alternate legacy names should be changed to `Webstores` when touching user-facing areas.

Original repo inspected: `C:\Users\thesi\Documents\GitHub\signguyai`

MVP repo inspected: `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP`

## Goal

Find the elaborate questionnaire maker from the original repo and decide how to reuse the idea in MVP for:

- Webstore-specific questionnaires.
- Regular client design/intake questionnaires.
- Employee training quiz questions.

The target should be a shared form maker, not three separate form systems that drift apart.

## Original Repo Source Files

Primary original form maker files:

- `C:\Users\thesi\Documents\GitHub\signguyai\frontend\src\pages\Questionnaires.js`
- `C:\Users\thesi\Documents\GitHub\signguyai\frontend\src\pages\PublicQuestionnaire.js`
- `C:\Users\thesi\Documents\GitHub\signguyai\frontend\src\pages\PortalForms.js`
- `C:\Users\thesi\Documents\GitHub\signguyai\backend\models\questionnaires.py`
- `C:\Users\thesi\Documents\GitHub\signguyai\backend\routes\questionnaires.py`
- `C:\Users\thesi\Documents\GitHub\signguyai\backend\routes\admin_portal.py`
- `C:\Users\thesi\Documents\GitHub\signguyai\backend\routes\portal.py`

Related original docs/tests:

- `C:\Users\thesi\Documents\GitHub\signguyai\QUESTIONNAIRE_SEND_FIX.md`
- `C:\Users\thesi\Documents\GitHub\signguyai\EVENT_WEBSTORE_QUESTIONNAIRE_README.md`
- `C:\Users\thesi\Documents\GitHub\signguyai\backend\tests\test_questionnaires.py`
- `C:\Users\thesi\Documents\GitHub\signguyai\backend\tests\test_questionnaire_nested_validation.py`
- `C:\Users\thesi\Documents\GitHub\signguyai\backend\tests\test_customer_portal_forms.py`
- `C:\Users\thesi\Documents\GitHub\signguyai\backend\tests\test_iteration155_questionnaire_webstore.py`

## What The Original Form Maker Had

The original form maker was a dynamic questionnaire builder, not just a hardcoded Webstores questionnaire.

Question types supported by the original model:

- `text`
- `textarea`
- `number`
- `email`
- `phone`
- `select`
- `multi_select`
- `radio`
- `checkbox`
- `date`
- `file_upload`
- `signature`
- `heading`
- `paragraph`

Question configuration supported:

- Stable question IDs.
- Labels.
- Descriptions.
- Placeholders.
- Required flags.
- Options for select/radio/checkbox/multi-select.
- Option value/label/description shape.
- Validation dictionary for min/max/pattern-style future validation.
- Conditional visibility with `depends_on`, `operator`, and `value`.
- Ordered questions.
- File accept types.
- Max file size.

Questionnaire configuration supported:

- Tenant scope.
- Name.
- Description.
- Category.
- Question list.
- Draft/active/archived status.
- Default questionnaire flag.
- Thank-you message.
- Response count.
- Created/updated metadata.
- Optional Webstore link.
- Prefilled answers.
- Locked answer IDs for provider-set fields.
- Last sent timestamp.

Original categories:

- Vehicle wrap.
- Signage.
- Apparel.
- Print.
- Webstores.
- Custom.
- General.

Original management UI features:

- List questionnaires.
- Filter by category.
- Create new questionnaire.
- Start from prebuilt template.
- Edit questions.
- Add/remove questions.
- Choose question type.
- Add/remove options.
- Mark required.
- Duplicate questionnaire.
- Delete questionnaire.
- Toggle draft/active.
- View responses.
- Copy public share link.
- Send by email.
- Send to customer portal concept.
- Custom thank-you message.

Original public form features:

- Public `/questionnaire/:questionnaireId` style renderer.
- Customer name/email collection.
- Type-aware answer defaults.
- Required-field validation.
- Email validation on customer info.
- Public rendering for text, textarea, number, email, phone, date, select, radio, checkbox, multi-select, heading, paragraph, and file upload placeholder.
- Locked/prefilled answer behavior.
- Thank-you screen after submit.

Original backend behavior:

- `GET /api/questionnaires`
- `GET /api/questionnaires/templates`
- `POST /api/questionnaires/from-template/{template_id}`
- `POST /api/questionnaires`
- `GET /api/questionnaires/{questionnaire_id}`
- `PUT /api/questionnaires/{questionnaire_id}`
- `DELETE /api/questionnaires/{questionnaire_id}`
- `POST /api/questionnaires/{questionnaire_id}/duplicate`
- `GET /api/questionnaires/public/{questionnaire_id}`
- `POST /api/questionnaires/public/{questionnaire_id}/submit`
- `GET /api/questionnaires/{questionnaire_id}/responses`
- `GET /api/questionnaires/responses/{response_id}`
- `DELETE /api/questionnaires/responses/{response_id}`
- `POST /api/questionnaires/{questionnaire_id}/send-email`

Original validation behavior:

- Backend walks both flat `questions` and nested `sections[*].questions`.
- Non-input types `heading` and `paragraph` are skipped.
- Required fields are enforced.
- Empty strings and empty arrays are treated as missing.
- Conditional hidden fields are not required.
- Locked fields are skipped because they are provider-prefilled.
- Email and phone formats have basic backend validation.

Original portal form behavior:

- Staff/admin can send a questionnaire request to a customer portal through `portal_form_requests`.
- Customer portal lists pending/in-progress/completed forms.
- Opening a form marks it in progress.
- Submitting a form creates a questionnaire response.
- Submission also creates a text document and shares it into the customer portal document area.
- Form request status becomes completed.
- Customer notification is created.

Important mismatch found:

- `frontend/src/pages/Questionnaires.js` calls `/api/questionnaires/{id}/send-to-portal`.
- The backend portal form send route found is `/api/admin-portal/forms/send`.
- So we should port the capability, not blindly copy that exact endpoint.

## Original Webstore Questionnaire Templates

The rich Webstore questionnaires live in `backend\models\questionnaires.py`.

Found Webstore-related templates include:

- Event Web Store Setup Questionnaire.
- Fundraiser Web Store Setup Questionnaire.
- Team / School Web Store Setup Questionnaire.
- Business / Company Web Store Setup Questionnaire.

The original Event template is very detailed. It includes contact, event info, launch/close dates, public/private visibility, logo/artwork uploads, products wanted, design personalization, sponsor logos, fulfillment, confirmation emails, donations, Stripe payout questions, owner approval, final acknowledgments, signature, and date.

We already ported much of this questionnaire content into MVP Webstores defaults, but not the full general-purpose builder.

## Current MVP State

MVP currently has three separate form-like systems.

### 1. Webstores Questionnaires

Files:

- `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP\backend\app\models\webstore.py`
- `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP\backend\app\services\webstore_setup.py`
- `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP\backend\app\routers\webstores.py`
- `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP\backend\app\routers\webstore_owner_portal.py`
- `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP\frontend\src\pages\WebstoreOwnerPortalPage.jsx`
- `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP\frontend\src\pages\WebstoreDetailPage.jsx`

Current shape:

- Webstore-only questionnaire templates.
- Sections with questions.
- Store-type defaults.
- Owner portal render/submit.
- Draft/save/submit.
- Staff review.
- Safe answer mapping/apply.
- Setup files.
- Notifications on submission.

Supported current Webstores owner portal question types:

- `paragraph`
- `select`
- `checkbox`
- `textarea`
- `date`
- `email`
- `number`
- default text input.

Missing versus original builder:

- General questionnaire library.
- Category tabs.
- Create/edit UI for arbitrary questionnaires.
- Duplicate/archive/status management UI.
- Public standalone questionnaire link/token system.
- Customer portal form request workflow.
- Rich response browser for all form types.
- Signature field rendering.
- File upload field as a question type. Webstores has setup files, but not integrated as reusable form field questions.
- Conditional visibility.
- Validation dictionary support.
- Multi-select distinct from checkbox.
- Radio field rendering.
- Phone type.
- Locked/prefilled answer behavior as a shared generic feature.

### 2. Regular Client Intake / Design Forms

MVP has intake submission models and intake UI, but no general form-maker route found.

Related files:

- `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP\backend\app\models\intake_submission.py`
- `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP\frontend\src\components\intake\IntakeItemForm.jsx`

Current state:

- Intake exists as a workflow concept.
- It is not backed by the original-style dynamic questionnaire builder.
- There is no shared questionnaire builder for design/client forms yet.

### 3. Employee Training Quizzes

Files:

- `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP\backend\app\models\training_definition.py`
- `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP\backend\app\services\training_service.py`
- `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP\backend\app\routers\training.py`
- `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP\backend\app\routers\portal_employee.py`
- `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP\frontend\src\components\training\TrainingDefinitionDialog.jsx`
- `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP\frontend\src\portal\employee\MyTrainingAssignmentDetailPage.jsx`

Current shape:

- Training definitions store `quiz_questions` directly.
- Each quiz question is `{id, prompt, choices, correct_index}`.
- Manager builder supports adding questions, choices, and one correct answer.
- Employee portal renders choices but strips answer keys.
- Backend scores quiz attempts and stores attempt history.

Important rule to preserve:

- `correct_index` must never be serialized to the employee portal.
- Quiz scoring must remain backend-only.

Missing versus desired shared form maker:

- Training quiz builder cannot reuse richer question types.
- No true/false shortcut, multi-answer scoring, explanation text, images/files, question banks, randomization, or weighted scoring.
- It is separate from all customer/Webstore questionnaire logic.

## Recommendation

Build one shared Form Maker foundation in MVP, then adapt it for three use cases.

Do not copy the original repo as-is. Port the proven concepts and improve the architecture to fit MVP's current backend patterns.

### Shared Foundation

Create a shared form system with these core records:

- `form_templates`
- `form_template_versions`
- `form_requests`
- `form_responses`
- `form_response_mappings`
- `form_attachments`

Keep compatibility aliases in the UI where needed:

- Webstores can call them `Questionnaires`.
- Client/design workflows can call them `Forms` or `Design Questionnaires`.
- Employee training can call them `Quizzes`.

Use one underlying schema so the builder is shared.

### Shared Question Schema

Port and extend the original question schema:

- `id`
- `type`
- `label`
- `description`
- `placeholder`
- `required`
- `options`
- `validation`
- `conditional`
- `order`
- `accept_file_types`
- `max_file_size_mb`
- `prefill_value`
- `locked`
- `visibility`
- `help_text`
- `section_id`

Initial shared field types should include:

- Text.
- Textarea.
- Number.
- Email.
- Phone.
- Date.
- Dropdown select.
- Radio buttons.
- Checkboxes.
- Multi-select.
- File upload.
- Signature.
- Heading.
- Paragraph.

Training-only quiz extensions:

- Correct answer(s).
- Points.
- Explanation.
- Required passing score.
- Attempt limit.
- Randomize choice order later.

Store these scoring fields in a manager-only/private config area so employee portal responses never expose answer keys.

### Shared Builder UI

Build a modern MVP version of the original `Questionnaires.js`:

- Template list.
- Category/module filters.
- Create from template.
- Create blank.
- Edit form metadata.
- Add/remove/reorder sections.
- Add/remove/reorder questions.
- Choose field type.
- Required toggle.
- Placeholder/description.
- Options editor.
- File upload settings.
- Signature toggle.
- Conditional visibility editor.
- Preview form.
- Duplicate.
- Archive/restore.
- Publish active version.
- View responses.

This should become the reusable builder for:

- Webstore setup questionnaires.
- Customer/client design questionnaires.
- Employee training quizzes.

### Renderer Components

Create shared frontend components:

- `FormBuilder`
- `FormRenderer`
- `FormResponseViewer`
- `QuestionEditor`
- `QuestionInput`
- `OptionEditor`
- `ConditionalRuleEditor`

Then use wrappers:

- `WebstoreQuestionnaireBuilder`
- `ClientDesignFormBuilder`
- `TrainingQuizBuilder`

This prevents Webstores, customer intake, and employee training from each building their own incompatible form renderer.

### Backend Services

Create shared services:

- `forms_service.py`
- `form_templates_service.py`
- `form_requests_service.py`
- `form_responses_service.py`
- `form_mapping_service.py`

Do not create duplicate Webstore/client/training form storage.

Each module should attach context:

- Webstore request: `context_type = "webstore"`, `context_id = webstore_id`, owner/customer identity.
- Client design request: `context_type = "customer"` or `context_type = "intake"`, customer/job/intake IDs.
- Training quiz: `context_type = "training_assignment"`, training assignment ID and employee ID.

### Response Mapping

Webstores need mapping from answers into setup fields.

Client/design questionnaires need mapping into:

- Customer record fields.
- Intake submission fields.
- Quote/job notes.
- File attachments.
- Follow-up tasks.

Training quizzes need mapping into:

- Quiz attempt.
- Score.
- Pass/fail.
- Training assignment status.
- Certification/practical signoff flow where applicable.

Mapping must be explicit and auditable.

### Security Rules

Carry these rules forward:

- Tenant scope on every internal form/template/request/response.
- Public links must use secure request tokens, not raw template IDs for sensitive workflows.
- Owner/customer/employee portal routes must enforce identity scope server-side.
- Public-safe DTOs must exclude internal fields.
- Training answer keys must never leave backend/admin manager views.
- File uploads must use the existing file/document storage rules, not base64 blobs in form responses.
- Original response answers must be preserved.
- Applying answers to setup/customer/training records must create activity/audit events.

## Suggested Stage Placement

Add a form-maker substage before deeper Webstores work:

### Stage 3A - Shared Form Maker Foundation

Build shared form template/version/request/response models, services, and renderer components.

### Stage 3B - Webstore Questionnaire Adapter

Move Webstores questionnaire templates onto the shared form maker while preserving current send/owner portal/review/apply behavior.

### Stage 3C - Client Design Questionnaire Adapter

Use the same form maker for regular client forms and customer/design intake.

### Stage 3D - Training Quiz Adapter

Use the same builder for employee quizzes, but preserve backend-only scoring and never expose answer keys to employees.

## Porting Priority

1. Port the original question schema and validation concepts.
2. Build shared renderer and builder components.
3. Migrate Webstores questionnaire templates into shared form templates.
4. Add customer/client design form requests.
5. Adapt training quiz creation to use the shared builder with private scoring metadata.
6. Add response mapping for each module.
7. Only then continue heavy Webstores questionnaire UI work.

## Do Not Port Blindly

Avoid these original-repo issues:

- Do not use public raw questionnaire IDs for sensitive assigned forms.
- Do not store real uploaded file contents inside answers.
- Do not copy the mismatched `send-to-portal` frontend endpoint without designing the backend route.
- Do not let Webstores, client forms, and employee quizzes diverge into separate builders.
- Do not expose training answer keys in portal DTOs.
- Do not make frontend-only validation authoritative.

## Conclusion

The original repo had the right product idea: a real dynamic questionnaire maker. MVP currently has only narrower, module-specific pieces.

The best path is to build one shared Form Maker foundation and then use adapters for Webstores questionnaires, client design questionnaires, and employee training quizzes. That gives the app the elaborate form-maker behavior the original repo had without repeating the prior mistake of creating separate systems for each module.
