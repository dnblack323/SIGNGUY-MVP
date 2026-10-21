"""Help Center taxonomy, onboarding slug registry and contextual-help definitions.

``CATEGORIES`` is the single source for category keys, labels and order; the API serves it so the UI never
hard-codes a second copy. ``ONBOARDING_ARTICLE_SLUGS`` is the contract used by ``/help/docs?article=<slug>``
links; see ``docs/modules/help_article_slug_registry.md``.
"""
from __future__ import annotations

from typing import Any

CATEGORIES: list[dict[str, Any]] = [
    {"key": "getting_started", "label": "Getting Started", "description": "What SIGNGUY is, how it fits together, and how to set up your shop."},
    {"key": "shop_management", "label": "Shop Management", "description": "Company settings, employees, permissions, time and scheduling."},
    {"key": "customers_sales", "label": "Customers & Sales", "description": "Customers, quotes, orders, invoices, payments and the Customer Portal."},
    {"key": "production", "label": "Production", "description": "Work orders, the production board, artwork, approvals and installation."},
    {"key": "pricing", "label": "Pricing", "description": "Pricing Foundation, materials, labor, equipment, methods and calculators."},
    {"key": "webstores", "label": "Webstores", "description": "Set up, approve, launch and fulfill customer Webstores."},
    {"key": "wrap_lab", "label": "Wrap Lab", "description": "Vehicle wrap projects from measurements to installation."},
    {"key": "business", "label": "Business Management", "description": "Finances, expenses, reports, inventory, documents and your dashboard."},
    {"key": "ai_tools", "label": "AI & Advanced Tools", "description": "The Business Assistant, Studio tools, AI permissions and limits."},
    {"key": "support", "label": "Support & Troubleshooting", "description": "Common problems, FAQ, contacting support, bug reports and feature requests."},
    {"key": "role_guides", "label": "Role Guides", "description": "Short guides for owners and staff."},
    {"key": "release_notes", "label": "What's New", "description": "Release history of shipped changes."},
]

CATEGORY_KEYS = [c["key"] for c in CATEGORIES]

# Stable slugs that onboarding links to. Keep in sync with docs/modules/help_article_slug_registry.md.
ONBOARDING_ARTICLE_SLUGS: dict[str, str] = {
    "getting_started": "getting-started",
    "company_profile": "company-profile",
    "pricing_setup": "pricing-setup",
    "employees_and_permissions": "employees-and-permissions",
    "production_workflow": "production-workflow",
    "customer_portal": "customer-portal",
    "first_order": "first-order",
    "webstore_setup": "webstore-setup",
}


def _ctx(surface_key: str, help_key: str, module: str, title: str, body: str, article_slug: str, *keywords: str) -> dict[str, Any]:
    return {"surface_key": surface_key, "help_key": help_key, "module": module, "title": title, "body": body, "article_slug": article_slug, "keywords": list(keywords)}


CONTEXTUAL_HELP: list[dict[str, Any]] = [
    _ctx("onboarding.dashboard", "progress", "onboarding", "Setup progress", "Required steps drive launch readiness; skipped required steps remain visible until completed.", "guided-onboarding", "progress", "required"),
    _ctx("pricing.quiz", "approval", "pricing", "Pricing approval", "Quiz suggestions are provisional. Pricing settings change only after owner/admin approval.", "pricing-setup", "pricing", "approval"),
    _ctx("templates.editor", "placeholders", "templates", "Placeholders", "Use approved placeholder tokens and preview missing values before saving reusable templates.", "templates-and-placeholders", "placeholder"),
    _ctx("billing.subscriptions", "failed_payment", "billing", "Failed payments", "Failed-payment states are informational in help; Subscriptions remains the billing source of truth.", "subscription-and-billing", "billing"),
    _ctx("studio.assistant", "assistant_boundary", "ai", "Assistant boundary", "The Business Assistant proposes actions and waits for your confirmation before changing records.", "business-assistant", "assistant"),
    _ctx("pricing.foundation", "methods", "pricing", "Pricing methods", "A pricing method is the rule used to turn costs into a price, such as cost plus or per square foot. Which methods you can pick depends on the product category.", "pricing-methods", "method", "markup"),
    _ctx("pricing.foundation", "labor_rates", "pricing", "Labor rates", "Hourly rates for production and installation work feed every estimate. Include burden (taxes, benefits) so labor is not under-priced.", "materials-labor-equipment", "labor", "hourly"),
    _ctx("pricing.foundation", "overhead", "pricing", "Overhead", "Default overhead spreads shop running costs across jobs as a percentage. Changing it affects new estimates, not saved quotes or invoices.", "materials-labor-equipment", "overhead"),
    _ctx("production.workflows", "stages", "production", "Production stages", "Stages are the steps a Work Order moves through, such as Design, Production and Installation. Edit stages here; the Production Board shows live work by stage.", "production-workflow", "stage", "workflow"),
    _ctx("orders.list", "create", "orders", "Creating an order", "An order holds the customer, the order items and their prices. Production items can then become a Work Order.", "first-order", "order", "new order"),
    _ctx("invoices.detail", "deposits", "invoices", "Deposits and payments", "Record payments on the invoice. If the order requires a deposit before production, work stays blocked until enough payment is recorded.", "invoices-and-payments", "deposit", "payment"),
    _ctx("employees.list", "permissions", "employees", "Employee permissions", "Owners and admins can manage everything in the shop; staff get a narrower set of permissions. Link an employee record to a login so they can clock in.", "employees-and-permissions", "role", "permission"),
    _ctx("webstores.questionnaire", "questionnaire", "webstores", "Webstore questionnaire", "The questionnaire collects the store owner's details after you send the information packet. Review the answers, request changes if needed, then continue setup.", "webstore-information-packets-and-questionnaires", "questionnaire", "packet"),
    _ctx("webstores.fulfillment", "fulfillment", "webstores", "Webstore fulfillment", "Fulfillment settings control how orders from a live Webstore are handled. Webstore orders become regular orders for production.", "webstore-fulfillment", "fulfillment", "shipping"),
    _ctx("approvals.center", "artwork", "approvals", "Artwork approvals", "Customer approvals of artwork and proofs are tracked here. Production should not start on an item until its approval is current.", "approvals-and-proofs", "artwork", "proof", "approval"),
]
