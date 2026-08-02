import "@testing-library/jest-dom";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";
import FormBuilder from "@/components/forms/FormBuilder";
import FormRenderer from "@/components/forms/FormRenderer";
import PublicFormRequestPage from "@/pages/PublicFormRequestPage";
import { getPublicFormRequest, submitPublicFormResponse } from "@/lib/forms";

jest.mock("@/lib/forms", () => ({
  getPublicFormRequest: jest.fn(),
  submitPublicFormResponse: jest.fn(),
}));

jest.mock("sonner", () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

const donorSections = [
  {
    id: "main",
    title: "Main",
    questions: [
      { key: "heading", label: "Store Setup", type: "heading" },
      {
        key: "paragraph",
        label: "Answer the questions below.",
        type: "paragraph",
      },
      { key: "name", label: "Name", type: "text", required: true },
      { key: "details", label: "Details", type: "textarea" },
      { key: "quantity", label: "Quantity", type: "number" },
      { key: "email", label: "Email", type: "email" },
      { key: "phone", label: "Phone", type: "phone" },
      {
        key: "dropdown",
        label: "Dropdown",
        type: "select",
        options: [{ value: "a", label: "A" }],
      },
      {
        key: "multi",
        label: "Multi",
        type: "multi_select",
        options: [{ value: "x", label: "X" }],
      },
      {
        key: "radio",
        label: "Radio",
        type: "radio",
        options: [
          { value: "yes", label: "Yes" },
          { value: "no", label: "No" },
        ],
      },
      {
        key: "conditional",
        label: "Conditional Details",
        type: "text",
        required: true,
        conditional: { depends_on: "radio", operator: "equals", value: "yes" },
      },
      {
        key: "checks",
        label: "Checks",
        type: "checkbox",
        options: [{ value: "one", label: "One" }],
      },
      { key: "date", label: "Date", type: "date" },
      { key: "upload", label: "Upload", type: "file_upload" },
      { key: "signature", label: "Signature", type: "signature" },
    ],
  },
];

test("shared FormRenderer supports donor field types and conditional visibility", () => {
  const onAnswersChange = jest.fn();
  const { container, rerender } = renderWithProviders(
    <FormRenderer
      sections={donorSections}
      answers={{ radio: "no" }}
      onAnswersChange={onAnswersChange}
    />,
  );

  expect(screen.getByText("Store Setup")).toBeInTheDocument();
  expect(screen.getByText("Answer the questions below.")).toBeInTheDocument();
  expect(
    screen.getByTestId("shared-form-answer-name").querySelector("input"),
  ).toBeInTheDocument();
  expect(
    screen.getByTestId("shared-form-answer-details").querySelector("textarea"),
  ).toBeInTheDocument();
  expect(
    screen
      .getByTestId("shared-form-answer-quantity")
      .querySelector('input[type="number"]'),
  ).toBeInTheDocument();
  expect(
    screen
      .getByTestId("shared-form-answer-email")
      .querySelector('input[type="email"]'),
  ).toBeInTheDocument();
  expect(
    screen.getByTestId("shared-form-answer-phone").querySelector("input"),
  ).toBeInTheDocument();
  expect(
    screen.getByTestId("shared-form-answer-dropdown").querySelector("select"),
  ).toBeInTheDocument();
  expect(
    screen
      .getByTestId("shared-form-answer-multi")
      .querySelector('input[type="checkbox"]'),
  ).toBeInTheDocument();
  expect(
    screen
      .getByTestId("shared-form-answer-radio")
      .querySelector('input[type="radio"]'),
  ).toBeInTheDocument();
  expect(
    screen
      .getByTestId("shared-form-answer-checks")
      .querySelector('input[type="checkbox"]'),
  ).toBeInTheDocument();
  expect(
    screen
      .getByTestId("shared-form-answer-date")
      .querySelector('input[type="date"]'),
  ).toBeInTheDocument();
  expect(
    screen
      .getByTestId("shared-form-answer-upload")
      .querySelector('input[type="file"]'),
  ).toBeInTheDocument();
  expect(
    screen
      .getByTestId("shared-form-answer-signature")
      .querySelector("textarea"),
  ).toBeInTheDocument();
  expect(
    screen.queryByTestId("shared-form-answer-conditional"),
  ).not.toBeInTheDocument();

  rerender(
    <FormRenderer
      sections={donorSections}
      answers={{ radio: "yes" }}
      onAnswersChange={onAnswersChange}
    />,
  );
  expect(
    screen.getByTestId("shared-form-answer-conditional").querySelector("input"),
  ).toBeInTheDocument();

  fireEvent.change(
    container.querySelector('[data-testid="shared-form-answer-name"] input'),
    { target: { value: "Alice" } },
  );
  expect(onAnswersChange).toHaveBeenCalledWith({ radio: "yes", name: "Alice" });
});

test("shared FormBuilder edits field details without creating a Webstores-only builder", () => {
  const onChange = jest.fn();
  renderWithProviders(
    <FormBuilder
      value={{
        name: "Webstore Intake",
        module: "webstores",
        private_config: {
          adapter: "webstore_questionnaire",
          store_type: "event",
        },
        sections: [{ id: "main", title: "Main", questions: [] }],
      }}
      onChange={onChange}
    />,
  );

  fireEvent.click(screen.getByText("Add Question"));
  expect(onChange).toHaveBeenCalledWith(
    expect.objectContaining({
      sections: [
        expect.objectContaining({
          questions: [expect.objectContaining({ type: "text" })],
        }),
      ],
    }),
  );
  expect(screen.getByText("Webstore questionnaire type")).toBeInTheDocument();
});

test("public form request page validates required answers and submits through shared responses", async () => {
  getPublicFormRequest.mockResolvedValue({
    request: { id: "req-1", context_type: "webstore", context_id: "ws-1" },
    template: {
      id: "tmpl-1",
      name: "Owner Questionnaire",
      sections: [
        {
          id: "main",
          title: "Main",
          questions: [
            {
              key: "store_name",
              label: "Store name",
              type: "text",
              required: true,
            },
            {
              key: "needs_more",
              label: "Need more?",
              type: "radio",
              options: [
                { value: "yes", label: "Yes" },
                { value: "no", label: "No" },
              ],
            },
            {
              key: "more_details",
              label: "More details",
              type: "text",
              required: true,
              conditional: {
                depends_on: "needs_more",
                operator: "equals",
                value: "yes",
              },
            },
          ],
        },
      ],
    },
  });
  submitPublicFormResponse.mockResolvedValue({ id: "resp-1" });

  renderWithProviders(<PublicFormRequestPage />, {
    route: "/forms/request/token-1",
    path: "/forms/request/:token",
  });

  expect(await screen.findByText("Owner Questionnaire")).toBeInTheDocument();
  expect(screen.getByText("Required answers missing")).toBeInTheDocument();
  const submitButton = screen.getByText("Submit answers");
  expect(submitButton).toBeDisabled();

  const storeName = within(
    screen.getByTestId("shared-form-answer-store_name"),
  ).getByRole("textbox");
  fireEvent.change(storeName, { target: { value: "Team Store" } });
  await waitFor(() =>
    expect(
      screen.queryByText("Required answers missing"),
    ).not.toBeInTheDocument(),
  );
  expect(submitButton).not.toBeDisabled();

  fireEvent.click(submitButton);
  await waitFor(() =>
    expect(submitPublicFormResponse).toHaveBeenCalledWith(
      "token-1",
      expect.objectContaining({
        answers: expect.objectContaining({ store_name: "Team Store" }),
      }),
    ),
  );
  expect(await screen.findByText("Answers submitted")).toBeInTheDocument();
});
