"""Demonstration sales and production scenarios (fictional). Money is integer cents; dates are offsets from "today".

A scenario drives one customer's job through the canonical chain:
quote -> order -> work order -> production stages -> invoice -> payments.
"""
from __future__ import annotations

# Customers that are tax exempt in the demo (schools, nonprofits, churches).
TAX_EXEMPT = {"maple_pta", "raptors", "foodbank", "fireaux", "boosters", "stbrigid"}
TAX_RATE_BP = 725  # 7.25% on taxable customers

# Stage owner by stage key (employee keys from data_shop.STAFF); anything else goes to the production manager.
STAGE_OWNER = {
    "design": "aisha", "art_prep": "aisha", "preflight": "aisha", "proof_approval": "aisha",
    "print": "tomas", "cut": "tomas", "weed": "tomas", "mask": "tomas", "production": "tomas", "print_or_cut": "tomas", "laminate": "tomas",
    "lamination": "tomas", "finish": "tomas", "cure_or_finish": "tomas", "mount": "tomas",
    "schedule": "devon", "prep": "devon", "install": "devon", "inspection": "devon", "wrap": "devon",
}


def item(name, desc, qty, unit_cents, category, product_type, w=None, h=None, production=True):
    return {"item_name": name, "description": desc, "quantity": qty, "unit_price_cents": unit_cents, "category": category,
            "product_type": product_type, "width_inches": w, "height_inches": h, "production_required": production,
            "selected_price_source": "manual", "manual_override_reason": "Demonstration pricing"}


# production: stages_done = stages completed per workflow; then `state` for the next stage:
#   None | "start" | ("wait", reason) | ("block", reason). wo_path = work order transitions to apply in order.
# payments: [(cents, method, days_ago, reference)]. invoice: None | "draft" | "issued" (+ due_days from today, may be negative).
SCENARIOS = [
    dict(key="harbor_windows", customer="harbor", job="Fall Window Graphics", due=-12, order="completed",
         items=[item("Window lettering - hours & logo", "Cut vinyl storefront lettering, 2 windows", 1, 38500, "cut_vinyl", "window_lettering", 96, 40),
                item("Seasonal leaf accents", "Cut vinyl leaf accents (set of 6)", 6, 2200, "cut_vinyl", "decal", 12, 12),
                item("Installation", "On-site window installation", 1, 15000, "installation", "service")],
         wo=dict(priority="normal", assign=["tomas", "devon"], path=["released", "queued", "in_progress", "ready", "completed"], stages_done="all", state=None),
         invoice=dict(kind="issued", due=-20), payments=[(None, "check", 14, "CHK-2041")]),
    dict(key="harbor_aframes", customer="harbor", job="Sidewalk A-Frame Signs (2)", due=6, order="in_production",
         items=[item("A-frame sign panels", "4mm coroplast panels printed 2 sides, 24x36", 4, 5800, "rigid_signs", "a_frame_panel", 24, 36),
                item("A-frame frames", "Heavy-duty swinging A-frame frames", 2, 8900, "rigid_signs", "hardware", production=False)],
         wo=dict(priority="normal", assign=["tomas"], path=["released", "queued", "in_progress"], stages_done=1, state="start"),
         invoice=dict(kind="issued", due=12), payments=[(0.5, "card", 3, "DEMO-CARD-1182")]),
    dict(key="delgado_van5", customer="delgado", job="Van #5 Full Wrap", due=21, order="confirmed",
         items=[item("Full wrap - Ford Transit 250 (high roof)", "Printed + laminated cast wrap, full coverage, design included", 1, 485000, "vehicle_graphics", "full_wrap", 0, 0)],
         wo=dict(priority="high", assign=["aisha", "devon"], path=["released", "queued", "in_progress"], stages_done=0, state="start"),
         invoice=dict(kind="issued", due=21), payments=[(0.5, "bank_transfer", 5, "ACH-DEMO-7720")]),
    dict(key="delgado_doors", customer="delgado", job="Fleet Door Lettering - 3 Vans", due=4, order="ready",
         items=[item("Door lettering sets", "Cut vinyl company name, phone and license numbers (set per van)", 3, 22500, "cut_vinyl", "vehicle_lettering", 40, 18),
                item("Installation", "On-site installation at customer shop", 3, 7500, "installation", "service")],
         wo=dict(priority="normal", assign=["tomas", "devon"], path=["released", "queued", "in_progress", "ready"], stages_done="all", state=None),
         invoice=dict(kind="issued", due=15), payments=[], install_event=dict(days=3, hours=4, title="Install: Delgado fleet door lettering", employee="devon")),
    dict(key="summit_pickup", customer="summit", job="Pickup Partial Wrap + Tailgate Logo", due=18, order="confirmed",
         items=[item("Partial wrap - pickup", "Printed + laminated partial wrap with tailgate logo", 1, 189000, "vehicle_graphics", "partial_wrap", 0, 0)],
         wo=dict(priority="normal", assign=["aisha"], path=["released", "queued"], stages_done=1, state=("wait", "Waiting on customer approval of wrap proof")),
         invoice=dict(kind="issued", due=18), payments=[]),
    dict(key="northgate_wayfinding", customer="northgate", job="Interior Wayfinding & Door Signs (14)", due=25, order="confirmed",
         items=[item("ADA door signs", "ADA-compliant room signs with braille, 8x8", 14, 6800, "rigid_signs", "ada_sign", 8, 8),
                item("Directory board", "Lobby directory board, 24x36 PVC", 1, 24500, "rigid_signs", "directory", 24, 36)],
         wo=dict(priority="normal", assign=["aisha"], path=["released", "queued"], stages_done=0, state=("wait", "Waiting for artwork - customer logo vector files")),
         invoice=dict(kind="draft", due=25), payments=[]),
    dict(key="northgate_monument", customer="northgate", job="Monument Sign Face Panels", due=35, order="confirmed",
         items=[item("Monument sign faces", "Aluminum composite faces with cut vinyl lettering, 2 sides", 2, 118000, "rigid_signs", "monument_face", 72, 36)],
         wo=dict(priority="low", assign=["tomas"], path=["released", "queued", "blocked"], stages_done=0, state=("block", "On hold - landlord permit pending")),
         invoice=dict(kind="draft", due=35), payments=[]),
    dict(key="foodbank_banners", customer="foodbank", job="Spring Food Drive Banners (4)", due=-1, order="ready",
         items=[item("Food drive banner 3x8", "13oz banner, hemmed and grommeted, full color", 4, 11500, "banners", "banner", 96, 36),
                item("Hems & grommets", "Finishing for banners", 4, 1200, "banners", "finishing", production=False)],
         wo=dict(priority="normal", assign=["tomas"], path=["released", "queued", "in_progress", "ready"], stages_done="all", state=None),
         invoice=dict(kind="issued", due=14), payments=[], discount_cents=5000),
    dict(key="foodbank_shirts", customer="foodbank", job="Volunteer T-Shirts (60)", due=14, order="in_production",
         items=[item("Volunteer tee - 1 color front", "Navy cotton tees, 1-color front print, adult sizes", 60, 1450, "apparel", "tshirt")],
         wo=dict(priority="normal", assign=["tomas"], path=["released", "queued", "in_progress"], stages_done=1, state="start"),
         invoice=dict(kind="issued", due=14), payments=[(0.5, "check", 6, "CHK-7731")]),
    dict(key="fireaux_hoodies", customer="fireaux", job="Pancake Breakfast Hoodies (48)", due=-25, order="completed",
         items=[item("Charcoal hoodie - 2 color chest", "Fleece hoodie with 2-color left chest print", 48, 3450, "apparel", "hoodie")],
         wo=dict(priority="normal", assign=["tomas"], path=["released", "queued", "in_progress", "ready", "completed"], stages_done="all", state=None),
         invoice=dict(kind="issued", due=-30), payments=[(None, "cash", 28, "CASH-DEMO-0412")]),
    dict(key="raptors_fence", customer="raptors", job="Outfield Fence Banners (6)", due=9, order="in_production",
         items=[item("Sponsor fence banner 2x6", "13oz mesh banner, sponsor artwork, grommets every 24in", 6, 9800, "banners", "banner", 72, 24)],
         wo=dict(priority="high", assign=["tomas"], path=["released", "queued", "in_progress"], stages_done=1, state="start"),
         invoice=dict(kind="issued", due=9), payments=[(50000, "check", 8, "CHK-1190")]),
    dict(key="brightway_van", customer="brightway", job="Detail Van Partial Graphics", due=-8, order="completed",
         items=[item("Partial vehicle graphics", "Printed + laminated side panels and rear door graphics", 1, 142000, "vehicle_graphics", "partial_wrap", 0, 0)],
         wo=dict(priority="normal", assign=["aisha", "devon"], path=["released", "queued", "in_progress", "ready", "completed"], stages_done="all", state=None),
         invoice=dict(kind="issued", due=-10), payments=[(None, "card", 9, "DEMO-CARD-5521")]),
    dict(key="patel_menu", customer="patel", job="Holiday Menu Board Panels", due=-30, order="completed",
         items=[item("Menu board panels", "PVC foam board panels with printed menu, 24x36", 3, 7400, "rigid_signs", "menu_board", 24, 36)],
         wo=dict(priority="rush", assign=["tomas"], path=["released", "queued", "in_progress", "ready", "completed"], stages_done="all", state=None),
         invoice=dict(kind="issued", due=-20), payments=[]),
    dict(key="whitfield_decal", customer="whitfield", job="Memorial Window Decal", due=-40, order="completed",
         items=[item("Memorial rear-window decal", "Cut vinyl memorial decal, 18x10", 1, 7500, "cut_vinyl", "decal", 18, 10)],
         wo=dict(priority="normal", assign=["tomas"], path=["released", "queued", "in_progress", "ready", "completed"], stages_done="all", state=None),
         invoice=dict(kind="issued", due=-45), payments=[(None, "card", 44, "DEMO-CARD-0093")]),
    dict(key="raman_wedding", customer="raman", job="Wedding Welcome Sign + Seating Chart", due=24, order="confirmed",
         items=[item("Welcome sign 24x36", "Printed PVC board welcome sign", 1, 11500, "rigid_signs", "event_sign", 24, 36),
                item("Seating chart 36x48", "Printed PVC board seating chart", 1, 15500, "rigid_signs", "event_sign", 36, 48)],
         wo=dict(priority="normal", assign=["aisha"], path=["released", "queued"], stages_done=1, state=("wait", "Waiting for customer approval of proof")),
         invoice=dict(kind="issued", due=24), payments=[(0.5, "card", 2, "DEMO-CARD-3310")]),
    dict(key="oakline_signs", customer="oakline", job="Yard Signs (50) + Riders", due=7, order="in_production",
         items=[item("Yard sign 18x24 double sided", "4mm coroplast yard signs with H-stakes", 50, 1250, "rigid_signs", "yard_sign", 18, 24),
                item("Rider panel 6x24", "Coroplast rider panels", 50, 480, "rigid_signs", "rider", 6, 24)],
         wo=dict(priority="normal", assign=["tomas"], path=["released", "queued", "in_progress"], stages_done=1, state="start"),
         invoice=dict(kind="issued", due=7), payments=[]),
    dict(key="ironclad_walls", customer="ironclad", job="Gym Wall Graphics + Floor Decals", due=16, order="in_production",
         items=[item("Wall graphics", "Printed and laminated wall graphics, 3 walls", 3, 64000, "digital_print", "wall_graphic", 144, 72),
                item("Floor decals", "Printed floor decals with anti-slip laminate", 12, 4800, "digital_print", "floor_decal", 24, 24),
                item("Installation", "On-site wall and floor installation", 1, 45000, "installation", "service")],
         wo=dict(priority="high", assign=["tomas", "devon"], path=["released", "queued", "in_progress"], stages_done=2, state="start"),
         invoice=dict(kind="issued", due=16), payments=[(0.5, "bank_transfer", 7, "ACH-DEMO-4408")],
         install_event=dict(days=15, hours=6, title="Install: Ironclad wall graphics + floor decals", employee="devon")),
    dict(key="cedar_banners", customer="cedarhollow", job="Harvest Festival Banner Set", due=20, order="confirmed",
         items=[item("Festival entrance banner 4x10", "13oz banner with pole pockets", 1, 24500, "banners", "banner", 120, 48),
                item("Sandwich board inserts", "Printed coroplast inserts, 24x36", 4, 5200, "rigid_signs", "insert", 24, 36)],
         wo=dict(priority="normal", assign=["aisha"], path=["released", "queued"], stages_done=0, state=("wait", "Waiting for artwork - festival lineup not final")),
         invoice=dict(kind="draft", due=20), payments=[]),
    dict(key="stbrigid_bazaar", customer="stbrigid", job="Christmas Bazaar Banner", due=-18, order="completed",
         items=[item("Bazaar banner 3x8", "13oz banner, hems and grommets", 1, 14500, "banners", "banner", 96, 36)],
         wo=dict(priority="normal", assign=["tomas"], path=["released", "queued", "in_progress", "ready", "completed"], stages_done="all", state=None),
         invoice=dict(kind="issued", due=-25), payments=[(None, "check", 20, "CHK-0553")]),
    dict(key="boosters_designs", customer="boosters", job="Spirit Wear Design Package", due=12, order="confirmed",
         items=[item("Team spirit-wear artwork", "Design 3 logo variations for spirit wear", 1, 25000, "apparel", "design_service", production=False),
                item("Sample hoodies", "Sample hoodies for approval", 3, 4200, "apparel", "hoodie")],
         wo=dict(priority="normal", assign=["aisha"], path=["released", "queued", "in_progress"], stages_done=0, state="start"),
         invoice=dict(kind="issued", due=12), payments=[]),
]

# Open quotes that are NOT converted: (key, customer, job, final status, items, days until expiry)
OPEN_QUOTES = [
    ("bell_foodtruck", "bell", "Food Truck Wrap Estimate", "draft",
     [item("Food truck wrap", "Full wrap estimate, vehicle TBD", 1, 380000, "vehicle_graphics", "full_wrap", 0, 0)], 30),
    ("harbor_menuboards", "harbor", "Spring Menu Boards", "draft",
     [item("Interior menu boards", "PVC menu boards, 24x36", 3, 7400, "rigid_signs", "menu_board", 24, 36)], 30),
    ("delgado_van6", "delgado", "Van #6 Full Wrap", "viewed",
     [item("Full wrap - Ford Transit 250", "Printed + laminated cast wrap", 1, 485000, "vehicle_graphics", "full_wrap", 0, 0)], 14),
    ("summit_trailer", "summit", "Equipment Trailer Graphics", "approved",
     [item("Trailer graphics", "Cut vinyl logo + printed side panels", 1, 96000, "vehicle_graphics", "trailer", 0, 0)], 21),
    ("northgate_bid", "northgate", "Exterior Pylon Sign Bid", "declined",
     [item("Pylon sign", "Illuminated pylon sign, outsourced fabrication", 1, 960000, "rigid_signs", "pylon", 0, 0)], 7),
]
