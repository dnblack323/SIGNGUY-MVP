import { render, screen } from "@testing-library/react";
import { webstoreStatusLabel } from "@/components/webstores/detail/WebstoreDetailUtils";

test("the launch_ready status is labelled as setup complete, not launch ready", () => {
  expect(webstoreStatusLabel("launch_ready")).toBe("setup complete");
  expect(webstoreStatusLabel("questionnaire_sent")).toBe("questionnaire sent");
});
