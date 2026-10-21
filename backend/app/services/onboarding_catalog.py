"""Guided Onboarding V1 — the three-stage step catalog.

Pure data. Every step points at the real MVP feature that owns the setting
(`route`) and, where the setting is small enough to edit inline, names the
`form` the guided UI renders. Completion is *detected* from the owning
collection in `services/onboarding._canonical_completion`; nothing here is
a copy of shop configuration.

Task fields:
  stage        quick_start | standard | advanced
  level        required | recommended | optional
  detect       "canonical" (derived from real records) or "manual" (no record
               exists to inspect — the owner confirms with an explicit
               "Mark as reviewed" action, never by pressing Next)
  feature_key  commercial entitlement that gates the step (advanced stage)
  help_slug    Help Center article slug (`/help/docs?article=<slug>`)
"""
from __future__ import annotations

from typing import Any

STAGES: list[dict[str, str]] = [
    {"key": "quick_start", "title": "Quick Start", "summary": "Get the shop operational with the minimum setup."},
    {"key": "standard", "title": "Standard Setup", "summary": "Finish normal business configuration and prepare the major workflows."},
    {"key": "advanced", "title": "Advanced Optimization", "summary": "Optional systems, automation and analytics. Nothing here blocks daily work."},
]


def _t(task_key: str, title: str, stage: str, level: str, what: str, why: str, **extra: Any) -> dict[str, Any]:
    return {
        "task_key": task_key,
        "title": title,
        "stage": stage,
        "level": level,
        "what": what,
        "why": why,
        "dependencies": extra.pop("dependencies", []),
        "detect": extra.pop("detect", "canonical"),
        "route": extra.pop("route", None),
        "route_label": extra.pop("route_label", None),
        "form": extra.pop("form", None),
        "feature_key": extra.pop("feature_key", None),
        "help_slug": extra.pop("help_slug", None),
    }


ONBOARDING_TASKS: list[dict[str, Any]] = [
    # ---- Stage 1 — Quick Start -------------------------------------------------
    _t("company_profile", "Business information", "quick_start", "required",
       "Your shop name and legal name.", "Appears on quotes, invoices and customer emails.",
       form="company", route="/settings/company", route_label="Company settings", help_slug="company-profile"),
    _t("company_contact", "Address and contact", "quick_start", "required",
       "Phone, email, website and street address.", "Customers need a way to reach you and invoices need a return address.",
       dependencies=["company_profile"], form="contact", route="/settings/company", route_label="Company settings", help_slug="company-profile"),
    _t("branding", "Logo and branding", "quick_start", "optional",
       "Brand color and email signature (logo upload lives in Documents).", "Keeps customer-facing documents on brand.",
       form="branding", route="/settings/company", route_label="Company settings", help_slug="branding"),
    _t("labor_rates", "Labor and pricing basics", "quick_start", "required",
       "Hourly labor rates, markup and deposit — saved into Pricing Foundation.", "Quotes cannot be priced realistically without your labor rates.",
       dependencies=["company_profile"], form="labor_rates", route="/pricing-foundation", route_label="Pricing Foundation", help_slug="pricing-foundation"),
    _t("production_workflow", "Production workflow", "quick_start", "required",
       "The default stages an order moves through in production.", "Work orders and the production board follow this workflow.",
       form="workflow", route="/settings/production-workflows", route_label="Production workflows", help_slug="production-workflows"),
    _t("first_employee", "First team member", "quick_start", "recommended",
       "Add one employee record.", "Employees can be scheduled, clock in and be assigned production work.",
       form="employee", route="/team/employees", route_label="Employees", help_slug="employees"),
    _t("payment_preferences", "Payment preferences", "quick_start", "recommended",
       "Default payment terms and invoice footer. Stripe is optional and set up later.", "Prints on every invoice so customers know how and when to pay.",
       form="payment_prefs", route="/settings/company", route_label="Company settings", help_slug="invoices-and-payments"),
    _t("portal_preferences", "Customer portal preferences", "quick_start", "recommended",
       "Choose whether customers get a portal for approvals and invoices.", "Decides whether customers can review proofs and pay online.",
       form="portal_prefs", route="/settings", route_label="Settings", help_slug="customer-portal"),
    _t("first_customer", "First customer", "quick_start", "required",
       "Create a real customer record.", "Every quote and order belongs to a customer.",
       form="customer", route="/customers", route_label="Customers", help_slug="customers"),
    _t("first_order", "First order", "quick_start", "required",
       "Create a real order for that customer.", "Confirms the whole path from customer to production works.",
       dependencies=["first_customer"], form="order", route="/work-orders", route_label="Orders", help_slug="orders"),

    # ---- Stage 2 — Standard Setup ----------------------------------------------
    _t("employees_permissions", "Employees and permissions", "standard", "recommended",
       "Add the rest of the team and give each person the right role.", "Roles limit who sees pricing, finances and settings.",
       route="/team/employees", route_label="Employees", help_slug="employees"),
    _t("time_clock", "Time Clock", "standard", "optional",
       "Decide whether staff clock in and out in MVP.", "Feeds timesheets and labor-cost reporting.",
       detect="manual", route="/team/time-clock", route_label="Time Clock", help_slug="time-clock"),
    _t("production_stages", "Production stages", "standard", "recommended",
       "Review or customize stages per product category.", "Banners, wraps and signs rarely share one timeline.",
       detect="manual", route="/settings/production-workflows", route_label="Production workflows", help_slug="production-workflows"),
    _t("order_workflow", "Order workflow preferences", "standard", "optional",
       "Review how orders move from quote to production to invoice.", "Prevents surprises when staff start moving work.",
       detect="manual", route="/orders", route_label="Orders", help_slug="orders"),
    _t("scheduling", "Scheduling", "standard", "optional",
       "Set up the shop schedule and installs.", "Shows promised dates and crew availability.",
       detect="manual", route="/shop-schedule", route_label="Shop schedule", help_slug="shop-schedule"),
    _t("pricing_foundation", "Pricing Foundation", "standard", "recommended",
       "Review category defaults, overhead and target margin.", "Calculators use these values on every quote.",
       dependencies=["labor_rates"], route="/pricing-foundation", route_label="Pricing Foundation", help_slug="pricing-foundation"),
    _t("materials", "Materials", "standard", "recommended",
       "Add the materials you buy most.", "Material cost drives accurate quotes.",
       route="/inventory", route_label="Inventory", help_slug="materials"),
    _t("equipment", "Equipment", "standard", "optional",
       "Add printers, cutters and vehicles.", "Lets production stages require the right equipment.",
       route="/team/equipment", route_label="Equipment", help_slug="equipment"),
    _t("categories", "Categories", "standard", "recommended",
       "Review pricing category methods and defaults.", "Each category prices differently.",
       dependencies=["labor_rates"], route="/pricing-foundation", route_label="Pricing Foundation", help_slug="pricing-foundation"),
    _t("documents", "Documents", "standard", "optional",
       "Upload your logo and standard documents.", "Keeps proofs, contracts and photos with the order.",
       route="/documents", route_label="Documents", help_slug="documents"),
    _t("notifications", "Notification preferences", "standard", "recommended",
       "Choose which events notify your team.", "Keeps approvals and payments from being missed.",
       form="notifications", route="/settings", route_label="Settings", help_slug="notifications"),
    _t("customer_portal", "Customer portal", "standard", "optional",
       "Invite a customer to the portal.", "Confirms customers can see their proofs and invoices.",
       dependencies=["portal_preferences"], route="/customers", route_label="Customers", help_slug="customer-portal"),
    _t("webstore_fulfillment", "Webstore fulfillment preferences", "standard", "optional",
       "Pickup and shipping preferences for webstores.", "Only needed if you sell through a webstore.",
       detect="manual", feature_key="webstores", route="/webstores", route_label="Webstores", help_slug="webstores"),
    _t("invoice_deposit", "Invoice and deposit settings", "standard", "recommended",
       "Review deposit percentage and invoice defaults.", "Controls what customers are asked to pay up front.",
       dependencies=["labor_rates"], route="/pricing-foundation", route_label="Pricing Foundation", help_slug="invoices-and-payments"),

    # ---- Stage 3 — Advanced Optimization ---------------------------------------
    _t("advanced_pricing", "Advanced pricing configuration", "advanced", "optional",
       "Per-category method tuning and comparisons.", "Fine-tunes margins by product type.",
       detect="manual", route="/pricing-foundation", route_label="Pricing Foundation", help_slug="pricing-foundation"),
    _t("reporting_profitability", "Reporting and profitability", "advanced", "optional",
       "Review profitability reports.", "Shows which work makes money.",
       detect="manual", route="/reports", route_label="Reports", help_slug="reports"),
    _t("production_analytics", "Production analytics", "advanced", "optional",
       "Review stage timing and bottlenecks.", "Finds where orders wait.",
       detect="manual", route="/work-orders/board", route_label="Production board", help_slug="production-workflows"),
    _t("inventory_management", "Inventory management", "advanced", "optional",
       "Reorder points, vendors and purchase orders.", "Avoids stock-outs on common materials.",
       detect="manual", route="/inventory", route_label="Inventory", help_slug="inventory"),
    _t("employee_scheduling", "Employee scheduling", "advanced", "optional",
       "Team schedule and time off.", "Plans crews around installs.",
       detect="manual", route="/team/schedule", route_label="Team schedule", help_slug="shop-schedule"),
    _t("webstores", "Webstores", "advanced", "optional",
       "Set up a team or event webstore.", "Sell spirit wear and event merchandise online.",
       detect="manual", feature_key="webstores", route="/webstores", route_label="Webstores", help_slug="webstores"),
    _t("wrap_lab", "Wrap Lab", "advanced", "optional",
       "Vehicle wrap design workflow.", "Estimates and mockups for wrap jobs.",
       detect="manual", feature_key="wrap_lab", route="/wrap-lab", route_label="Wrap Lab", help_slug="wrap-lab"),
    _t("business_assistant", "Business Assistant", "advanced", "optional",
       "AI help answering questions about your shop.", "Optional. Requires an AI plan.",
       detect="manual", feature_key="business_assistant", route="/studio/assistant", route_label="Business Assistant", help_slug="business-assistant"),
    _t("automation_preferences", "Automation preferences", "advanced", "optional",
       "Decide which events should notify staff or customers automatically.", "Cuts manual follow-up.",
       detect="manual", route="/settings", route_label="Settings", help_slug="notifications"),
    _t("ai_feature_access", "AI feature access", "advanced", "optional",
       "Review credits, limits and who can use AI tools.", "Optional. Onboarding never requires an AI subscription.",
       detect="manual", feature_key="ai_studio", route="/settings/ai-credits", route_label="AI credits", help_slug="ai-credits"),
    _t("customer_communications", "Advanced customer communications", "advanced", "optional",
       "Templates, questionnaires and messaging.", "Consistent, professional customer messages.",
       detect="manual", route="/templates", route_label="Templates", help_slug="templates"),
]

TASKS_BY_KEY: dict[str, dict[str, Any]] = {t["task_key"]: t for t in ONBOARDING_TASKS}
