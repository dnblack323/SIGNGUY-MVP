"""Webstore Starter pack question content, version 2.

Built from shared sections (organization, dates, products/artwork, fulfillment,
proceeds, policies) plus a short section per store type. Every answer key that
configures the store has a row in ``SAFE_ANSWER_MAPPING``. Shops customise their
installed Form Maker copies; this module changes only with a pack release.

No Stripe, bank, routing, card or signature questions (V1 shop-merchant model).
"""
from __future__ import annotations

from typing import Any

QUESTIONNAIRE_CONTENT_VERSION = 2
ACKNOWLEDGEMENT_VERSION = "webstore_intake_ack_2026_10"
ACKNOWLEDGEMENT_TEXT = "I confirm that the information I provided is accurate to the best of my knowledge."

YES_NO = [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]
YES_NO_UNSURE = [*YES_NO, {"value": "not_sure", "label": "Not sure"}]
PICKUP = ["shop_pickup", "organizer_pickup", "event_distribution"]
GROUP_PICKUP = ["organizer_pickup", "event_distribution"]
SHIPPING = ["individual_shipping", "bulk_shipping"]
PRODUCT_OPTIONS = [
    {"value": v, "label": label}
    for v, label in [
        ("tshirts", "T-shirts"), ("hoodies", "Hoodies"), ("crewnecks", "Crewnecks"), ("long_sleeve", "Long sleeve shirts"),
        ("hats", "Hats"), ("polos", "Polos"), ("yard_signs", "Yard signs"), ("banners", "Banners"),
        ("decals", "Decals / stickers"), ("drinkware", "Drinkware / tumblers"), ("bags", "Bags"), ("other", "Other"),
    ]
]
FULFILLMENT_OPTIONS = [
    {"value": "individual_shipping", "label": "Ship each order to the buyer"},
    {"value": "bulk_shipping", "label": "Ship all orders together to the organizer"},
    {"value": "shop_pickup", "label": "Buyers pick up at the shop"},
    {"value": "organizer_pickup", "label": "The organizer picks up all orders"},
    {"value": "event_distribution", "label": "Hand out orders at the event"},
    {"value": "local_delivery", "label": "Local delivery"},
]

PAYMENT_TEXT = (
    "How payments work: buyers pay the shop directly through the store checkout. The shop produces and delivers "
    "the merchandise and keeps the agreed production and fulfillment price. Your organization earns the agreed "
    "remaining proceeds, which the shop pays to you by check or bank transfer on the approved schedule. "
    "You never enter bank, routing or card details here. All financial terms are confirmed when you approve "
    "the store before it launches."
)
FINAL_SALE_TEXT = (
    "Custom merchandise is final sale. Exceptions: shop mistakes, manufacturing defects, incorrect items, "
    "unfulfilled orders, approved cancellations, and where the law requires a refund."
)


def q(key: str, label: str, type_: str = "text", *, required: bool = False, options: list | None = None,
      show_if: tuple | None = None, description: str | None = None) -> dict[str, Any]:
    """One question. ``show_if`` = (depends_on, operator, value)."""
    item: dict[str, Any] = {"key": key, "label": label, "type": type_, "required": required}
    if options:
        item["options"] = options
    if description:
        item["description"] = description
    if show_if:
        item["conditional"] = {"depends_on": show_if[0], "operator": show_if[1], "value": show_if[2]}
    return item


def _pickup_window(n: int) -> list[dict[str, Any]]:
    show = ("pickup_window_count", "greater_than", n - 1)
    return [
        q(f"pickup_window_{n}_date", f"Pickup window {n}: date", "date", required=True, show_if=show),
        q(f"pickup_window_{n}_start", f"Pickup window {n}: start time", "time", required=True, show_if=show),
        q(f"pickup_window_{n}_end", f"Pickup window {n}: end time", "time", required=True, show_if=show),
        q(f"pickup_window_{n}_location", f"Pickup window {n}: location (if different)", show_if=show),
        q(f"pickup_window_{n}_instructions", f"Pickup window {n}: instructions", "textarea", show_if=show),
    ]


BASE_SECTIONS: list[dict[str, Any]] = [
    {"id": "organization_contact", "title": "Your organization and contact", "questions": [
        q("organization_name", "Organization, team or business name", required=True),
        q("contact_name", "Main contact name", required=True),
        q("contact_email", "Main contact email", "email", required=True),
        q("contact_phone", "Main contact phone", "phone", required=True),
        q("decision_maker", "Who makes the final decisions for this store (if not you)?"),
    ]},
    {"id": "store_dates", "title": "Store name and dates", "questions": [
        q("store_name", "What should the store be called?", required=True),
        q("description", "Describe the store in a sentence or two", "textarea"),
        q("target_launch_at", "When should the store open?", "date", required=True),
        q("deadline_at", "When should ordering close?", "date", required=True),
        q("late_orders_allowed", "Accept late orders after the closing date?", "select", options=YES_NO),
        q("repeat_campaign", "Is this a one-time store or will it repeat?", "select", options=[
            {"value": "one_time", "label": "One time"}, {"value": "annual", "label": "Every year"},
            {"value": "seasonal", "label": "Each season"}, {"value": "ongoing", "label": "Always open"},
        ]),
    ]},
    {"id": "products_artwork", "title": "Products and artwork", "questions": [
        q("products_wanted", "Which products are you interested in?", "checkbox", required=True, options=PRODUCT_OPTIONS),
        q("product_notes", "Anything specific about colors, styles or sizes?", "textarea"),
        q("open_to_suggestions", "Would you like product recommendations from the shop?", "select", options=YES_NO),
        q("personalization_needed", "Should buyers be able to add names or numbers?", "select", required=True, options=YES_NO),
        q("personalization_details", "What can buyers personalize?", "textarea", required=True, show_if=("personalization_needed", "equals", "yes")),
        q("artwork_status", "Do you have artwork ready?", "select", required=True, options=[
            {"value": "ready", "label": "Yes, print-ready files"},
            {"value": "needs_cleanup", "label": "Yes, but it may need cleanup"},
            {"value": "need_design", "label": "No, we need a design created"},
        ]),
        q("logo_file", "Upload your logo or artwork", "file_upload", show_if=("artwork_status", "includes_any", ["ready", "needs_cleanup"])),
        q("design_notes", "Describe the design you want (wording, style, ideas)", "textarea", required=True, show_if=("artwork_status", "equals", "need_design")),
        q("brand_colors", "Colors to use"),
        q("colors_to_avoid", "Colors to avoid"),
        q("sponsors_included", "Will the design include sponsors?", "select", options=YES_NO),
        q("sponsor_names", "List the sponsor names", "textarea", required=True, show_if=("sponsors_included", "equals", "yes")),
        q("sponsor_logos", "Upload sponsor logos", "file_upload", show_if=("sponsors_included", "equals", "yes")),
    ]},
    {"id": "fulfillment", "title": "Getting orders to buyers", "questions": [
        q("fulfillment_methods", "How should buyers receive their orders?", "checkbox", required=True, options=FULFILLMENT_OPTIONS),
        q("shipping_notes", "Anything we should know about shipping?", "textarea", show_if=("fulfillment_methods", "includes_any", SHIPPING)),
        q("delivery_address", "Delivery address (for local delivery)", "textarea", required=True, show_if=("fulfillment_methods", "includes", "local_delivery")),
        q("pickup_location", "Where will orders be picked up or handed out?", required=True, show_if=("fulfillment_methods", "includes_any", GROUP_PICKUP)),
        q("pickup_instructions", "Pickup instructions for buyers", "textarea", show_if=("fulfillment_methods", "includes_any", PICKUP)),
        q("pickup_window_count", "How many pickup times do you need?", "select", options=[
            {"value": "1", "label": "One"}, {"value": "2", "label": "Two"}, {"value": "3", "label": "Three"},
        ], show_if=("fulfillment_methods", "includes_any", PICKUP)),
        *_pickup_window(1), *_pickup_window(2), *_pickup_window(3),
        q("bag_label_orders", "Should each order be bagged and labeled with the buyer's name?", "select", options=YES_NO,
          show_if=("fulfillment_methods", "includes_any", ["bulk_shipping", *GROUP_PICKUP])),
    ]},
    {"id": "proceeds", "title": "Proceeds and payouts", "questions": [
        q("payment_explainer", PAYMENT_TEXT, "paragraph"),
        q("earns_proceeds", "Will your organization earn money from this store?", "select", required=True, options=YES_NO_UNSURE),
        q("payout_recipient_name", "Who should payouts be made out to?", required=True, show_if=("earns_proceeds", "equals", "yes")),
        q("payout_method_preference", "Preferred payout method", "select", required=True, options=[
            {"value": "check", "label": "Check"}, {"value": "bank_transfer", "label": "Bank transfer (arranged with the shop)"},
            {"value": "other", "label": "Other"},
        ], show_if=("earns_proceeds", "equals", "yes")),
        q("payout_mailing_address", "Mailing address for checks", "textarea", required=True, show_if=("payout_method_preference", "equals", "check")),
        q("payout_contact", "Payout contact (name and email)", show_if=("earns_proceeds", "equals", "yes")),
    ]},
    {"id": "policies", "title": "Final details", "questions": [
        q("final_sale_notice", FINAL_SALE_TEXT, "paragraph"),
        q("notes", "Anything else we should know?", "textarea"),
        q("intake_acknowledgement", "Confirmation", "checkbox", required=True, options=[{"value": "confirmed", "label": ACKNOWLEDGEMENT_TEXT}]),
    ]},
]

TYPE_SECTIONS: dict[str, list[dict[str, Any]]] = {
    "fundraiser": [{"id": "fundraiser", "title": "Fundraiser", "questions": [
        q("fundraiser_name", "Fundraiser name"),
        q("fundraiser_purpose", "What is the money being raised for?", "textarea", required=True),
        q("fundraiser_goal_amount", "Fundraising goal in dollars (optional)", "number"),
        q("show_progress_bar", "Show fundraising progress on the store?", "select", options=YES_NO),
        q("profit_allocation_type", "How would you like proceeds calculated?", "select", required=True, options=[
            {"value": "percentage", "label": "A percentage of each sale"},
            {"value": "fixed_per_item", "label": "A fixed amount per item"},
            {"value": "decide_with_shop", "label": "Decide with the shop"},
        ]),
        q("profit_allocation_percentage", "Percentage of each sale", "number", required=True, show_if=("profit_allocation_type", "equals", "percentage")),
        q("fixed_amount_per_item", "Dollar amount per item", "number", required=True, show_if=("profit_allocation_type", "equals", "fixed_per_item")),
        q("allow_checkout_donations", "Let buyers add a donation at checkout?", "select", options=YES_NO),
        q("donation_amount_options", "Suggested donation amounts (for example 5, 10, 25)", show_if=("allow_checkout_donations", "equals", "yes")),
    ]}],
    "event": [{"id": "event", "title": "Event", "questions": [
        q("event_name", "Event name", required=True),
        q("event_start_at", "Event date", "date", required=True),
        q("event_location", "Event location", required=True),
        q("event_description", "Briefly describe the event", "textarea"),
        q("event_fundraiser_enabled", "Is the event also raising money?", "select", options=YES_NO),
        q("event_fundraiser_purpose", "What is the money being raised for?", "textarea", required=True, show_if=("event_fundraiser_enabled", "equals", "yes")),
        q("event_checkout_donations", "Let buyers add a donation at checkout?", "select", options=YES_NO, show_if=("event_fundraiser_enabled", "equals", "yes")),
    ]}],
    "team_school": [{"id": "team_school", "title": "Team or school", "questions": [
        q("group_name", "Team, school or club name", required=True),
        q("group_type", "What kind of group is this?", "select", options=[
            {"value": "sports_team", "label": "Sports team"}, {"value": "school", "label": "School"},
            {"value": "club", "label": "Club or activity"}, {"value": "boosters", "label": "Booster club"},
        ]),
        q("season", "Season or school year"),
        q("player_names_numbers", "Do items need player names or numbers?", "select", options=YES_NO),
        q("approval_contact", "Who must approve designs (coach, principal, director)?"),
        q("team_fundraising", "Is the store also raising money for the group?", "select", options=YES_NO),
        q("team_fundraiser_purpose", "What is the money being raised for?", "textarea", required=True, show_if=("team_fundraising", "equals", "yes")),
    ]}],
    "b2b": [{"id": "b2b", "title": "Business store", "questions": [
        q("b2b_preset", "What is this store for?", "select", required=True, options=[
            {"value": "employee_company", "label": "Employee / company apparel"},
            {"value": "customer_merch", "label": "Customer-facing merchandise"},
            {"value": "promo_events", "label": "Trade shows and promo events"},
            {"value": "client_gifts", "label": "Client gifts"},
        ]),
        q("access_policy_preference", "Who can see the store?", "select", required=True, options=[
            {"value": "public", "label": "Anyone with the link"}, {"value": "private", "label": "Only invited people"},
        ]),
        q("employee_access_method", "How should employees get access?", "select", options=[
            {"value": "invite", "label": "Invite only"}, {"value": "email_domain", "label": "Company email address"},
            {"value": "access_code", "label": "Access code"},
        ], show_if=("b2b_preset", "equals", "employee_company")),
        q("employee_audience", "Who should be able to order?", "textarea", show_if=("b2b_preset", "equals", "employee_company")),
        q("department_categories", "Departments or groups to organize by", "textarea", show_if=("b2b_preset", "equals", "employee_company")),
        q("allowance_notes", "Allowance, subsidy or payroll notes", "textarea", show_if=("b2b_preset", "equals", "employee_company")),
        q("catalog_change_frequency", "How often will products change?", "select", options=[
            {"value": "static", "label": "Rarely"}, {"value": "seasonal", "label": "Seasonally"}, {"value": "rotating", "label": "Often"},
        ]),
        q("billing_po_requirements", "Special billing or purchase-order requirements", "textarea"),
    ]}],
    "promotional": [{"id": "promotional", "title": "Promotional store", "questions": [
        q("brand_identity_name", "Athlete, creator, team or brand name", required=True),
        q("promotion_goal", "What is the goal of the promotion?", "textarea"),
        q("campaign_duration", "Is this ongoing or limited-time?", "select", options=[
            {"value": "ongoing", "label": "Ongoing"}, {"value": "limited", "label": "Limited-time"},
        ]),
        q("promo_channels", "Where will you promote the store?", "checkbox", options=[
            {"value": v, "label": label} for v, label in [("facebook", "Facebook"), ("instagram", "Instagram"), ("email", "Email"), ("sms", "Text messages"), ("flyers", "Flyers / QR code")]
        ]),
        q("promo_copy_notes", "Anything we should say in promotional copy?", "textarea"),
    ]}],
    "general": [{"id": "general", "title": "About the store", "questions": [
        q("store_purpose", "What is this store for?", "textarea", required=True),
        q("audience", "Who will be buying?", "textarea"),
    ]}],
}

STARTER_QUESTIONNAIRE_SECTIONS: dict[str, list[dict[str, Any]]] = {"base": BASE_SECTIONS, **TYPE_SECTIONS}
