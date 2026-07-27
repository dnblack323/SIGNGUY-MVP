import { render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import GoogleAuthCallback from "@/auth/GoogleAuthCallback";
import api from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";

jest.mock("@/lib/api", () => ({
  post: jest.fn(),
}));

jest.mock("@/auth/AuthContext", () => ({
  useAuth: jest.fn(),
}));

const mockNavigate = jest.fn();

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
  const refresh = jest.fn(async () => {
    expect(window.location.hash).toBe("");
  });
  useAuth.mockReturnValue({ refresh });
  api.post.mockResolvedValue({ data: { access_token: "app-token" } });

  render(
    <MemoryRouter>
      <GoogleAuthCallback />
    </MemoryRouter>,
  );

  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/auth/google/session", { session_id: "google-session-123" }));
  await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));

  expect(localStorage.getItem("signguy.token")).toBe("app-token");
  expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true });
});
