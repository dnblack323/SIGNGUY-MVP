import { render, screen } from "@testing-library/react";
import GuidedSetupModule from "@/components/webstores/GuidedSetupModule";
import { webstoreStatusLabel } from "@/components/webstores/detail/WebstoreDetailUtils";

const noop = () => {};

function renderLaunchStep(readiness) {
  render(
    <GuidedSetupModule
      store={{ id: "ws-1", status: "launch_ready", setup_state: "setup_complete", owner_approved_at: "2026-10-19T12:00:00Z" }}
      questionnaireSubmission={{ id: "sub-1", status: "reviewed" }}
      activeProducts={[{ id: "prod-1" }]}
      activePacket={{ id: "packet-1", status: "owner_approved", sent_at: "2026-10-18T12:00:00Z" }}
      setupFiles={[]}
      branding={{ draft: {} }}
      readiness={readiness}
      onShowTab={noop}
      onSendQuestionnaire={noop}
      onGeneratePacket={noop}
      onSendPacket={noop}
      onLaunch={noop}
    />,
  );
}

test("setup complete without verified payment never offers to launch the Webstore", () => {
  renderLaunchStep({
    setup_complete: true,
    ready_to_publish: false,
    payment_unavailable_reason: "Stripe integration is disabled for this foundation build.",
  });

  expect(screen.getByTestId("guided-setup-step-launch")).toHaveTextContent("Setup is complete. Publishing waits for verified payment setup.");
  expect(screen.getByTestId("guided-setup-step-launch")).not.toHaveTextContent("can be launched");
  expect(screen.queryByTestId("guided-launch-webstore")).not.toBeInTheDocument();
  expect(screen.getByTestId("guided-open-launch-gates")).toBeInTheDocument();
});

test("a Webstore that is ready to publish offers the launch action", () => {
  renderLaunchStep({ setup_complete: true, ready_to_publish: true });

  expect(screen.getByTestId("guided-setup-step-launch")).toHaveTextContent("Setup is complete and payment is verified.");
  expect(screen.getByTestId("guided-launch-webstore")).toBeInTheDocument();
});

test("the launch_ready status is labelled as setup complete, not launch ready", () => {
  expect(webstoreStatusLabel("launch_ready")).toBe("setup complete");
  expect(webstoreStatusLabel("questionnaire_sent")).toBe("questionnaire sent");
});
