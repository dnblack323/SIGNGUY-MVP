import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";

// Test helper: mount a component inside a QueryClient + MemoryRouter.
// Callers may pass `route` (initial URL) and `path` (route pattern) when using
// components that call `useParams`.
export function renderWithProviders(ui, { route = "/", path } = {}) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } },
  });
  const { render } = require("@testing-library/react");
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[route]}>
        {path ? (
          <Routes>
            <Route path={path} element={ui} />
            <Route path="*" element={ui} />
          </Routes>
        ) : (
          ui
        )}
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// Silence expected sonner toasts. Tests assert on toast side-effects via mocks.
export const flushAsync = () => new Promise((r) => setTimeout(r, 0));
