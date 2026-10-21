import React from "react";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Routes, Route } from "react-router-dom";
import { renderWithProviders } from "../test-utils";

jest.mock("@/auth/AuthContext", () => ({
  __esModule: true,
  useAuth: () => ({
    hasPerm: (perm) => ["help:read", "support:write", "subscription:read"].includes(perm),
    user: { id: "u1", tenant_id: "t1", role: "owner" },
  }),
}));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() }, Toaster: () => null }));
jest.mock("@/lib/help", () => ({
  ...jest.requireActual("@/lib/help"),
  listHelpArticles: jest.fn(),
  getHelpArticle: jest.fn(),
  listHelpCategories: jest.fn(),
  getContextualHelp: jest.fn(),
  sendHelpFeedback: jest.fn(),
  getFailedSubscriptionGuidance: jest.fn(),
}));

import { getContextualHelp, getFailedSubscriptionGuidance, getHelpArticle, helpDocsPath, listHelpArticles, listHelpCategories, sendHelpFeedback } from "@/lib/help";
import ContextualHelp from "@/components/help/ContextualHelp";
import MarkdownContent from "@/components/help/MarkdownContent";
import HelpCenterPage from "@/pages/HelpCenterPage";
import HelpDocsPage from "@/pages/HelpDocsPage";
import WhatsNewPage from "@/pages/WhatsNewPage";

const ARTICLES = [
  { id: "a1", slug: "getting-started", title: "Getting started with SIGNGUY", category: "getting_started", summary: "Short path.", aliases: [], related: [] },
  { id: "a2", slug: "first-order", title: "Creating your first order", category: "customers_sales", summary: "Run a job.", aliases: [], related: [] },
  { id: "a3", slug: "invoices-and-payments", title: "Invoices, deposits and payments", category: "customers_sales", summary: "Money.", aliases: ["invoices"], related: [] },
  { id: "a4", slug: "release-2026-10-21", title: "Webstores: one stage", category: "release_notes", summary: "Stage.", release: "2026.10.21", release_date: "2026-10-21", aliases: [], related: ["invoices-and-payments"], body: "- Item one" },
  { id: "a5", slug: "release-2026-10-15", title: "Home widgets", category: "release_notes", summary: "Widgets.", release: "2026.10.15", release_date: "2026-10-15", aliases: [], related: [], body: "- Item two" },
];
const CATEGORIES = [
  { key: "getting_started", label: "Getting Started", description: "Start here.", count: 1 },
  { key: "customers_sales", label: "Customers & Sales", description: "Sell.", count: 2 },
  { key: "release_notes", label: "What's New", description: "Releases.", count: 2 },
];

beforeEach(() => {
  jest.clearAllMocks();
  listHelpCategories.mockResolvedValue({ items: CATEGORIES });
  listHelpArticles.mockImplementation(async (params = {}) => {
    if (params.category === "release_notes") return { items: ARTICLES.filter((a) => a.category === "release_notes") };
    if (params.q) {
      const items = ARTICLES.filter((a) => a.title.toLowerCase().includes(params.q.toLowerCase())).map((a) => ({ ...a, snippet: `...${params.q}...` }));
      return { items };
    }
    return { items: ARTICLES };
  });
  getHelpArticle.mockImplementation(async (slug) => {
    const hit = ARTICLES.find((a) => a.slug === slug || a.aliases.includes(slug));
    if (!hit) throw new Error("not found");
    return { ...hit, body: "## Steps\n\nDo the **thing**. See [Orders](/help/docs?article=first-order).\n\n> A note.", links: [{ label: "Orders", to: "/orders" }] };
  });
  getFailedSubscriptionGuidance.mockResolvedValue({ dunning_state: "current", guidance: "ok" });
  sendHelpFeedback.mockResolvedValue({ id: "fb" });
  getContextualHelp.mockResolvedValue({ items: [{ id: "c1", help_key: "deposits", title: "Deposits", body: "Short body.", article_slug: "invoices-and-payments" }] });
});

const docs = (route) => renderWithProviders(<Routes><Route path="/help/docs" element={<HelpDocsPage />} /></Routes>, { route });

test("helpDocsPath builds the shared deep link contract", () => {
  expect(helpDocsPath("first-order")).toBe("/help/docs?article=first-order");
  expect(helpDocsPath()).toBe("/help/docs");
});

test("Help Center home offers search, getting started, categories and support", async () => {
  const user = userEvent.setup();
  renderWithProviders(<HelpCenterPage />);
  expect(await screen.findByTestId("help-center-page")).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: /getting started/i })).toBeInTheDocument();
  expect(await screen.findByTestId("help-category-customers_sales")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /contact support/i })).toHaveAttribute("href", "/help/contact");
  expect(screen.getByRole("link", { name: /report a bug/i })).toHaveAttribute("href", "/help/bugs");

  await user.type(screen.getByTestId("help-search-input"), "invoices");
  expect(await screen.findByTestId("help-search-results")).toHaveTextContent("Invoices, deposits and payments");
  await user.clear(screen.getByTestId("help-search-input"));
  await user.type(screen.getByTestId("help-search-input"), "zzz");
  expect(await screen.findByTestId("help-search-empty")).toBeInTheDocument();
});

test("Documentation home lists collapsible categories without release notes", async () => {
  const user = userEvent.setup();
  docs("/help/docs");
  expect(await screen.findByTestId("docs-home")).toBeInTheDocument();
  const group = await screen.findByTestId("docs-group-customers_sales");
  expect(screen.queryByTestId("docs-group-release_notes")).not.toBeInTheDocument();
  expect(group).toHaveAttribute("aria-expanded", "false");
  await user.click(group);
  expect(group).toHaveAttribute("aria-expanded", "true");
  expect(within(screen.getByTestId("docs-nav")).getByTestId("docs-nav-first-order")).toBeInTheDocument();
});

test("?article= deep link opens the article with breadcrumbs, links, related and previous/next", async () => {
  docs("/help/docs?article=first-order");
  expect(await screen.findByTestId("docs-article-title")).toHaveTextContent("Creating your first order");
  expect(screen.getByRole("heading", { name: "Steps" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Documentation" })).toHaveAttribute("href", "/help/docs");
  expect(screen.getAllByRole("link", { name: "Orders" }).map((a) => a.getAttribute("href"))).toEqual(expect.arrayContaining(["/help/docs?article=first-order", "/orders"]));
  expect(await screen.findByTestId("docs-prev")).toHaveAttribute("href", "/help/docs?article=getting-started");
  expect(screen.getByTestId("docs-next")).toHaveAttribute("href", "/help/docs?article=invoices-and-payments");
  expect(screen.getByRole("link", { name: /back to help center/i })).toHaveAttribute("href", "/help");
});

test("an alias resolves to its article and an unknown slug is handled gracefully", async () => {
  docs("/help/docs?article=invoices");
  expect(await screen.findByTestId("docs-article-title")).toHaveTextContent("Invoices, deposits and payments");
  renderWithProviders(<Routes><Route path="/help/docs" element={<HelpDocsPage />} /></Routes>, { route: "/help/docs?article=nope" });
  expect(await screen.findByText(/could not find that article/i)).toBeInTheDocument();
});

test("documentation search shows results and an empty state", async () => {
  const user = userEvent.setup();
  docs("/help/docs");
  const input = await screen.findByTestId("docs-search-input");
  await user.type(input, "first");
  expect(await screen.findByTestId("docs-search-results")).toHaveTextContent("Creating your first order");
  await user.clear(input);
  await user.type(input, "zzzz");
  expect(await screen.findByText(/No articles match/i)).toBeInTheDocument();
});

test("article feedback is sent once per choice", async () => {
  const user = userEvent.setup();
  docs("/help/docs?article=first-order");
  await user.click(await screen.findByRole("button", { name: "Helpful" }));
  await waitFor(() => expect(sendHelpFeedback).toHaveBeenCalledWith(expect.objectContaining({ article_slug: "first-order", helpful: true })));
});

test("What's New lists releases newest first with identifier, date and related docs", async () => {
  renderWithProviders(<WhatsNewPage />);
  const first = await screen.findByTestId("release-2026.10.21");
  const second = screen.getByTestId("release-2026.10.15");
  expect(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(first).toHaveTextContent("Release 2026.10.21");
  expect(first).toHaveTextContent("2026-10-21");
  expect(within(first).getByRole("link", { name: "Invoices, deposits and payments" })).toHaveAttribute("href", "/help/docs?article=invoices-and-payments");
});

test("contextual help links to the full article", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ContextualHelp surfaceKey="invoices.detail" module="invoices" />);
  await user.click(await screen.findByRole("button", { name: "Help" }));
  expect(await screen.findByTestId("contextual-help-article-deposits")).toHaveAttribute("href", "/help/docs?article=invoices-and-payments");
});

test("markdown renders safely: no raw HTML and no unsafe link schemes", () => {
  const { container } = renderWithProviders(<MarkdownContent markdown={'<script>alert(1)</script>\n\n[bad](javascript:alert(1)) and [ok](https://example.com)'} />);
  expect(container.querySelector("script")).toBeNull();
  expect(container.querySelector('a[href^="javascript"]')).toBeNull();
  expect(container.querySelector('a[href="https://example.com"]')).toHaveAttribute("rel", expect.stringContaining("noopener"));
});
