"""Webstore Starter pack question content (version 1 = the previous MVP default sections).

Edited only by pack releases; shops customise their installed Form Maker copies.
"""
from __future__ import annotations

from typing import Any


COMMON_PRODUCT_OPTIONS = [
    {"value": "tshirts", "label": "T-shirts"},
    {"value": "hoodies", "label": "Hoodies"},
    {"value": "crewnecks", "label": "Crewnecks"},
    {"value": "long_sleeve", "label": "Long sleeve shirts"},
    {"value": "hats", "label": "Hats"},
    {"value": "polos", "label": "Polos"},
    {"value": "yard_signs", "label": "Yard signs"},
    {"value": "banners", "label": "Banners"},
    {"value": "decals", "label": "Decals / stickers"},
    {"value": "drinkware", "label": "Drinkware / tumblers"},
    {"value": "bags", "label": "Bags"},
    {"value": "other", "label": "Other"},
]

YES_NO_OPTIONS = [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}, {"value": "not_sure", "label": "Not sure"}]

STARTER_QUESTIONNAIRE_SECTIONS: dict[str, list[dict[str, Any]]] = {
    "base": [
        {
            "id": "contact_store_basics",
            "title": "Contact and store basics",
            "questions": [
                {"key": "customer_name", "label": "Customer Name", "type": "text", "required": True},
                {"key": "organization_name", "label": "Organization / Business Name", "type": "text", "required": False},
                {"key": "phone_number", "label": "Phone Number", "type": "phone", "required": True},
                {"key": "email_address", "label": "Email Address", "type": "email", "required": True},
                {"key": "decision_maker", "label": "Who is the main decision-maker for this store?", "type": "text", "required": False},
                {"key": "store_name", "label": "What should the store be called?", "type": "text", "required": True},
                {"key": "description", "label": "Store description", "type": "textarea", "required": False},
                {"key": "target_launch_at", "label": "When do you want the store to launch?", "type": "date", "required": False},
                {"key": "deadline_at", "label": "Order deadline", "type": "date", "required": False},
                {"key": "audience", "label": "Audience", "type": "textarea", "required": False},
                {"key": "goals", "label": "Goals", "type": "textarea", "required": False},
            ],
        },
        {
            "id": "products_design",
            "title": "Products and design",
            "questions": [
                {"key": "products_wanted", "label": "What products do you want in the store? Check all that apply.", "type": "checkbox", "required": True, "options": COMMON_PRODUCT_OPTIONS},
                {"key": "design_count", "label": "How many designs do you want available?", "type": "select", "options": [
                    {"value": "1", "label": "1 design"},
                    {"value": "2_3", "label": "2-3 designs"},
                    {"value": "4_5", "label": "4-5 designs"},
                    {"value": "5_plus", "label": "More than 5"},
                    {"value": "not_sure", "label": "Not sure"},
                ]},
                {"key": "personalization_needed", "label": "Do products need personalization?", "type": "select", "options": YES_NO_OPTIONS},
                {"key": "personalization_details", "label": "If yes, describe what customers should be able to customize", "type": "textarea"},
                {"key": "apparel_colors", "label": "Preferred shirt / apparel colors", "type": "text"},
                {"key": "open_to_suggestions", "label": "Do you want product recommendations based on this store type?", "type": "select", "options": YES_NO_OPTIONS},
                {"key": "finished_artwork_status", "label": "Do you already have finished artwork?", "type": "select", "options": [
                    {"value": "yes", "label": "Yes"},
                    {"value": "no", "label": "No"},
                    {"value": "need_design", "label": "I need the design created"},
                ]},
                {"key": "design_notes", "label": "Design notes, style preferences, sponsor details, or required wording", "type": "textarea"},
            ],
        },
        {
            "id": "branding_fulfillment_approval",
            "title": "Branding, fulfillment, and approval",
            "questions": [
                {"key": "brand_colors", "label": "Colors to use", "type": "text"},
                {"key": "colors_to_avoid", "label": "Colors to avoid", "type": "text"},
                {"key": "pickup_instructions", "label": "Pickup date / time instructions", "type": "textarea"},
                {"key": "fulfillment_method", "label": "How should customers receive their orders?", "type": "select", "options": [
                    {"value": "individual_shipping", "label": "Individual shipping"},
                    {"value": "pickup_event", "label": "Pickup at event"},
                    {"value": "pickup_org", "label": "Pickup at organization / business"},
                    {"value": "pickup_shop", "label": "Pickup at our shop"},
                    {"value": "bulk_delivery", "label": "Bulk delivery to organizer"},
                    {"value": "not_sure", "label": "Not sure"},
                ]},
                {"key": "bag_label_orders", "label": "Should orders be individually bagged and labeled by customer name?", "type": "select", "options": YES_NO_OPTIONS},
                {"key": "approval_contact", "label": "Who should review the store before it goes live?", "type": "text"},
                {"key": "approval_required", "label": "Do you want to approve product names, pricing, images, and descriptions before launch?", "type": "select", "options": YES_NO_OPTIONS},
            ],
        }
    ],
    "b2b": [{"id": "b2b", "title": "Business / B2B", "questions": [
        {"key": "store_purpose", "label": "What is this store mainly for?", "type": "checkbox", "options": [
            {"value": "employee_apparel", "label": "Employee apparel / uniforms"},
            {"value": "customer_swag", "label": "Customer-facing swag / merch"},
            {"value": "promo_events", "label": "Tradeshow / promo events"},
            {"value": "client_gifts", "label": "Client gifts"},
            {"value": "internal_only", "label": "Internal-only / private store"},
        ]},
        {"key": "access_policy_preference", "label": "Should the store be public or private?", "type": "select", "options": [{"value": "public", "label": "Public - anyone with the link"}, {"value": "private", "label": "Private - invited users only"}]},
        {"key": "catalog_change_frequency", "label": "How often will products change?", "type": "select", "options": [{"value": "static", "label": "Rarely"}, {"value": "seasonal", "label": "Seasonally"}, {"value": "rotating", "label": "Frequently"}]},
        {"key": "billing_po_requirements", "label": "Special billing or PO requirements", "type": "textarea"},
    ]}],
    "fundraiser": [{"id": "fundraiser", "title": "Fundraiser settings", "questions": [
        {"key": "fundraiser_name", "label": "Fundraiser Name", "type": "text", "required": True},
        {"key": "goals", "label": "What is the money being raised for?", "type": "textarea"},
        {"key": "fundraiser_goal_amount", "label": "Fundraiser Goal Amount ($)", "type": "number"},
        {"key": "fundraiser_start_at", "label": "Fundraiser Start Date", "type": "date"},
        {"key": "deadline_at", "label": "Fundraiser End Date", "type": "date"},
        {"key": "show_progress_bar", "label": "Should a progress bar be shown publicly?", "type": "select", "options": YES_NO_OPTIONS},
        {"key": "show_total_raised_publicly", "label": "Show total amount raised publicly?", "type": "select", "options": YES_NO_OPTIONS},
        {"key": "profit_allocation_type", "label": "Profit allocation type", "type": "select", "options": [
            {"value": "percentage", "label": "Percentage of each sale"},
            {"value": "fixed_per_item", "label": "Fixed dollar amount per item"},
            {"value": "manual", "label": "Manual - decide after the store closes"},
        ]},
        {"key": "profit_allocation_percentage", "label": "Profit allocation percentage (%)", "type": "number"},
        {"key": "fixed_amount_per_item", "label": "Fixed profit allocation amount per item ($)", "type": "number"},
        {"key": "allow_checkout_donations", "label": "Allow checkout donations?", "type": "select", "options": YES_NO_OPTIONS},
        {"key": "donation_amount_options", "label": "Suggested donation amounts at checkout", "type": "text"},
    ]}],
    "event": [{"id": "event", "title": "Event details", "questions": [
        {"key": "event_name", "label": "Event Name", "type": "text", "required": True},
        {"key": "event_start_at", "label": "Event Date", "type": "date"},
        {"key": "event_location", "label": "Event Location", "type": "text"},
        {"key": "event_description", "label": "Briefly describe the event", "type": "textarea"},
        {"key": "event_type", "label": "Is this a one-time event or recurring event?", "type": "select", "options": [
            {"value": "one_time", "label": "One-time event"},
            {"value": "annual", "label": "Annual event"},
            {"value": "seasonal", "label": "Seasonal event"},
            {"value": "recurring", "label": "Recurring event"},
            {"value": "not_sure", "label": "Not sure"},
        ]},
        {"key": "allow_late_orders", "label": "Should late orders be allowed after the deadline?", "type": "select", "options": YES_NO_OPTIONS},
        {"key": "event_fundraiser_enabled", "label": "Is this event also raising funds?", "type": "select", "options": YES_NO_OPTIONS},
    ]}],
    "promotional": [{"id": "promotional", "title": "Promotional / team store", "questions": [
        {"key": "brand_identity_name", "label": "Athlete, creator, team, or brand name", "type": "text", "required": True},
        {"key": "promotion_goal", "label": "Promotion goal", "type": "textarea"},
        {"key": "campaign_duration", "label": "Is this ongoing or limited-time?", "type": "select", "options": [{"value": "ongoing", "label": "Ongoing"}, {"value": "limited", "label": "Limited-time"}, {"value": "not_sure", "label": "Not sure"}]},
        {"key": "promo_channels", "label": "Where will this be promoted?", "type": "checkbox", "options": [{"value": "facebook", "label": "Facebook"}, {"value": "instagram", "label": "Instagram"}, {"value": "email", "label": "Email"}, {"value": "sms", "label": "Text/SMS"}, {"value": "flyers", "label": "Flyers / QR code"}]},
        {"key": "promo_copy_notes", "label": "Anything we should include in launch/promotional copy?", "type": "textarea"},
    ]}],
    "employee": [{"id": "employee", "title": "Employee store", "questions": [
        {"key": "employee_audience", "label": "Who should be able to order?", "type": "textarea"},
        {"key": "department_categories", "label": "Departments or groups to organize by", "type": "textarea"},
        {"key": "access_policy_preference", "label": "How should access be restricted?", "type": "select", "options": [{"value": "invite", "label": "Invite only"}, {"value": "email_domain", "label": "Company email domain"}, {"value": "access_code", "label": "Access code"}, {"value": "not_sure", "label": "Not sure"}]},
        {"key": "allowance_notes", "label": "Allowance, subsidy, or payroll notes", "type": "textarea"},
    ]}],
    "general": [{"id": "general", "title": "General store notes", "questions": [
        {"key": "notes", "label": "Anything else we should know?", "type": "textarea", "required": False},
        {"key": "questionnaire_followup_needed", "label": "Is there anything you want us to follow up on before setup?", "type": "textarea", "required": False},
    ]}],
}

