import React from "react";
import { waitFor } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";
import GoogleAuthCallback from "@/auth/GoogleAuthCallback";
import api from "@/lib/api";

const mockRefresh = jest.fn();
const mockNavigate = jest.fn();

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    post: jest.fn(),
  },
}));

jest.mock("@/auth/AuthContext", () => ({
  __esModule: true,
  useAuth: () => ({ refresh: mockRefresh }),
}));

jest.mock("react-router-dom", () => {
  const actual = jest.requireActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.clear();
  window.history.replaceState(null, "", "/#session_id=google-session-123");
});

test("clears Google session hash before refreshing auth state", async () => {
  api.post.mockResolvedValue({ data: { access_token: "app-token" } });
  mockRefresh.mockImplementation(async () => {
    expect(window.location.hash).toBe("");
  });

  renderWithProviders(<GoogleAuthCallback />);

  await waitFor(() => {
    expect(api.post).toHaveBeenCalledWith("/auth/google/session", { session_id: "google-session-123" });
  });
  await waitFor(() => {
    expect(mockRefresh).toHaveBeenCalledTimes(1);
  });
  expect(localStorage.getItem("signguy.token")).toBe("app-token");
  expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true });
});
