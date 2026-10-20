"""Demonstration Webstores (fictional). Four stores at four different stages of the real setup workflow."""
from __future__ import annotations

from scripts.demo_shop.step_work import day

BASE_FULFILL_PICKUP = {"fulfillment_methods": ["organizer_pickup"], "pickup_location": "Front office",
                       "pickup_instructions": "Pick up at the front office during the listed window."}


def products(kind: str) -> list[dict]:
    """(name, short, long, type, method, cost, price, owner share) product sets by store."""
    sets = {
        "maple": [
            ("Spirit Tee", "Soft cotton tee with the school mascot", "Navy cotton tee, 1-color mascot print on the front.", "apparel", "screen_print", 650, 1800, 300, ["Youth M", "Adult S", "Adult M", "Adult L"]),
            ("Spirit Hoodie", "Cozy fleece hoodie with mascot", "Charcoal fleece hoodie, 2-color mascot print on the chest.", "apparel", "screen_print", 1550, 3800, 700, ["Youth L", "Adult M", "Adult L", "Adult XL"]),
            ("Mascot Decal", "Weatherproof mascot decal", "4-inch weatherproof vinyl decal for cars and water bottles.", "decal", "digital_print", 90, 500, 250, ["4 inch"]),
        ],
        "westfield": [
            ("Warriors Game Day Tee", "Performance tee for game days", "Red performance tee with the Warriors logo.", "apparel", "screen_print", 760, 2200, 500, ["Adult S", "Adult M", "Adult L"]),
            ("Warriors Hoodie", "Team hoodie", "Charcoal fleece hoodie with the Warriors logo.", "apparel", "screen_print", 1550, 4200, 900, ["Adult M", "Adult L", "Adult XL"]),
            ("Warriors Cap", "Embroidered cap", "Adjustable cap with embroidered logo.", "apparel", "embroidery", 820, 2400, 600, ["One size"]),
        ],
    }
    return sets[kind]


STORES = [
    dict(key="maple", customer="maple_pta", name="Maple Ridge Spirit Wear Fundraiser", store_type="fundraiser", purpose="Fall spirit-wear fundraiser for new playground equipment",
         contact=("Dana Whitaker", "dana.whitaker@mapleridge.example.com", "555-0101"), request_key="demo-maple-ridge", stage="approved",
         launch=(13, "Fall spirit wear opens"), close=(31, "Ordering closes"), logo="pta_logo",
         answers=dict(organization_name="Maple Ridge Elementary PTA", store_name="Maple Ridge Spirit Wear Fundraiser", products_wanted=["tshirts", "hoodies", "decals"],
                      personalization_needed="no", artwork_status="ready", design_notes="Use the school mascot on the front.", sponsors_included="no",
                      fulfillment_methods=["organizer_pickup"], pickup_location="Maple Ridge Elementary front office", pickup_instructions="Pick up during the front-office window.",
                      pickup_window_count="1", earns_proceeds="yes", payout_recipient_name="Maple Ridge Elementary PTA", payout_method_preference="check",
                      payout_mailing_address="410 School St, Fairhaven, OH 44801", fundraiser_name="Playground Fund", fundraiser_purpose="Fund new playground equipment",
                      profit_allocation_type="percentage", profit_allocation_percentage=20, allow_checkout_donations="yes", show_progress_bar="yes"),
         campaign="Every purchase helps fund new playground equipment at Maple Ridge Elementary.", products="maple"),
    dict(key="westfield", customer="boosters", name="Westfield Warriors Team Store", store_type="team_school", purpose="Winter sports team apparel store",
         contact=("Coach Brenda Hayes", "bhayes@westfieldhigh.example.com", "555-0113"), request_key="demo-westfield-warriors", stage="branding_review",
         launch=(20, "Team store opens"), close=(48, "Ordering closes"), logo="boosters_logo",
         answers=dict(organization_name="Westfield High Athletics Boosters", store_name="Westfield Warriors Team Store", products_wanted=["tshirts", "hoodies", "hats"],
                      personalization_needed="yes", personalization_details="Player names and numbers on the back of the game-day tee.", artwork_status="ready", sponsors_included="no",
                      fulfillment_methods=["shop_pickup"], pickup_instructions="Pick up at the shop counter.", pickup_window_count="1",
                      earns_proceeds="yes", payout_recipient_name="Westfield High Athletics Boosters", payout_method_preference="check",
                      payout_mailing_address="1 Warrior Way, Fairhaven, OH 44813", group_name="Westfield Warriors", group_type="boosters", season="Winter 2026-27",
                      player_names_numbers="yes", approval_contact="Coach Brenda Hayes", team_fundraising="yes", team_fundraiser_purpose="Fund new warm-up jackets for 9 teams"),
         products="westfield"),
    dict(key="ironclad", customer="ironclad", name="Ironclad Gear - Studio Merchandise", store_type="b2b", purpose="Branded studio merchandise for members and the community 5K",
         contact=("Mia Torres", "mia@ironcladfit.example.com", "555-0114"), request_key="demo-ironclad-gear", stage="returned_for_changes",
         launch=(25, "Merch store opens"), close=(60, "Ordering closes"), logo="ironclad_5k_logo",
         answers=dict(organization_name="Ironclad Fitness LLC", store_name="Ironclad Gear", products_wanted=["tshirts", "hoodies"], personalization_needed="no",
                      artwork_status="ready", sponsors_included="no", fulfillment_methods=["individual_shipping"], earns_proceeds="no",
                      payout_recipient_name="Ironclad Fitness LLC", payout_method_preference="bank_transfer", payout_mailing_address="480 Foundry St, Fairhaven, OH 44814",
                      b2b_preset="customer_merch", access_policy_preference="public", catalog_change_frequency="seasonal"),
         resubmit_note="Added a mailing address and confirmed the shipping method."),
    dict(key="cedar", customer="cedarhollow", name="Harvest Festival Merchandise", store_type="event", purpose="Event merchandise for the annual harvest festival",
         contact=("Sam Whitlock", "sam@cedarhollow.example.com", "555-0115"), request_key="demo-harvest-festival", stage="invited",
         launch=(30, "Festival store opens"), close=(75, "Ordering closes"), event_start=(80, "Harvest Festival"), event_location="Cedar Hollow Brewing Co. lot"),
]

# A small ledger of change-request style notes kept with the demonstration (shown in the report).
RETURN_REASON = "Please confirm how members will receive shipped orders and add the studio's mailing address."


def dates(spec: dict) -> dict:
    out = {"target_launch_at": day(spec["launch"][0]), "deadline_at": day(spec["close"][0])}
    if spec.get("event_start"):
        out["event_start_at"] = day(spec["event_start"][0])
    return out
