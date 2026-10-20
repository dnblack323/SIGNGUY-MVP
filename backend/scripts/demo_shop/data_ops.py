"""Demonstration expenses, schedule, calendar, tasks and time records (fictional)."""
from __future__ import annotations

# (days ago, category, description, cents, tax cents, payment method, vendor name or None, order scenario key or None, recurring)
EXPENSES = [
    (50, "rent", "Shop rent - September", 185000, 0, "bank_transfer", None, None, True),
    (20, "rent", "Shop rent - October", 185000, 0, "bank_transfer", None, None, True),
    (45, "utilities", "Electric and water - September", 39100, 0, "bank_transfer", None, None, False),
    (15, "utilities", "Electric and water - October", 42800, 0, "bank_transfer", None, None, False),
    (40, "insurance", "Commercial liability + vehicle policy", 31200, 0, "bank_transfer", None, None, True),
    (35, "materials", "Cast vinyl and laminate restock", 142300, 9948, "card", "Gulf Coast Sign Supply", None, False),
    (28, "materials", "Eco-solvent ink restock", 88400, 6188, "card", "Midwest Print Consumables", None, False),
    (12, "materials", "Wrap film for Van #5 (Delgado)", 118000, 0, "card", "Gulf Coast Sign Supply", "delgado_van5", False),
    (10, "materials", "Blank hoodies for Pancake Breakfast run", 52000, 0, "card", "Apparel Direct Blanks", "fireaux_hoodies", False),
    (22, "fuel", "Install van fuel - October", 18700, 0, "card", None, None, False),
    (18, "maintenance", "Printer service call and head cleaning", 28600, 0, "card", None, None, False),
    (30, "advertising", "Local direct-mail postcard campaign", 25000, 0, "card", None, None, False),
    (26, "software", "Design and RIP software subscriptions", 12900, 0, "card", None, None, True),
    (8, "shipping", "Freight - substrate delivery", 4200, 0, "card", "Gulf Coast Sign Supply", None, False),
]

# (shop-day offset, employee key, start hour, end hour, title, location)
SHIFT_TEMPLATE = {
    "carla": ("Production management", "Shop"),
    "devon": ("Installation / field work", "Shop + field"),
    "aisha": ("Design", "Design desk"),
    "tomas": ("Print and finishing", "Print room"),
}

# (days from today, start hour, duration hours, type, title, customer, order scenario or None, employee keys, location)
CALENDAR = [
    (2, 10, 1, "site_survey", "Site survey: Northgate Dental wayfinding", "northgate", "northgate_wayfinding", ["devon"], "Northgate Dental, 301 Northgate Plz"),
    (3, 8, 4, "installation", "Install: Delgado fleet door lettering", "delgado", "delgado_doors", ["devon", "tomas"], "Delgado Plumbing & Heating shop"),
    (4, 14, 1, "consultation", "Consultation: food truck wrap (Marcus Bell)", "bell", None, ["aisha"], "Shop"),
    (1, 15, 1, "custom", "Customer pickup: food drive banners", "foodbank", "foodbank_banners", ["carla"], "Shop front counter"),
    (10, 9, 2, "vehicle_dropoff", "Vehicle drop-off: Summit Peak pickup", "summit", "summit_pickup", ["devon"], "Shop garage"),
    (12, 8, 2, "vehicle_dropoff", "Vehicle drop-off: Delgado Van #5", "delgado", "delgado_van5", ["devon"], "Shop garage"),
    (19, 8, 8, "installation", "Install: Delgado Van #5 full wrap (day 1)", "delgado", "delgado_van5", ["devon", "tomas"], "Shop garage"),
    (20, 8, 8, "installation", "Install: Delgado Van #5 full wrap (day 2)", "delgado", "delgado_van5", ["devon", "tomas"], "Shop garage"),
    (15, 8, 6, "installation", "Install: Ironclad wall graphics + floor decals", "ironclad", "ironclad_walls", ["devon", "tomas"], "Ironclad Fitness Studio, 480 Foundry St"),
    (6, 13, 1, "customer_meeting", "Proof review: Summit Peak wrap", "summit", "summit_pickup", ["aisha"], "Shop"),
    (5, 9, 1, "internal_meeting", "Weekly production meeting", None, None, ["carla", "devon", "aisha", "tomas"], "Shop"),
    (-6, 9, 1, "internal_meeting", "Weekly production meeting", None, None, ["carla", "devon", "aisha", "tomas"], "Shop"),
]

# (title, description, priority, order scenario, customer, assignee, due days, final action)
TASKS = [
    ("Collect logo vector files from Northgate Dental", "Waiting on vector logo for the wayfinding signs.", "high", "northgate_wayfinding", "northgate", "aisha", 3, "start"),
    ("Send wrap proof to Summit Peak for approval", "Proof v2 is ready; customer approval is blocking production.", "high", "summit_pickup", "summit", "aisha", 1, "start"),
    ("Order more red cut vinyl", "Red 24in is down to 1 roll; reorder before the holiday rush.", "normal", None, None, "carla", 5, None),
    ("Confirm festival lineup with Cedar Hollow", "Banner copy cannot be finalized until the lineup is confirmed.", "normal", "cedar_banners", "cedarhollow", "carla", 7, "wait"),
    ("Pack and stage food drive banners", "Banners are done; stage at front counter for pickup.", "normal", "foodbank_banners", "foodbank", "tomas", 1, "complete"),
    ("Invoice follow-up: Patel Family Bakery", "Menu board invoice is past due; call Anita.", "high", "patel_menu", "patel", "carla", -2, "start"),
    ("Pre-wrap vehicle inspection: Delgado Van #5", "Photograph existing damage before wrap install.", "high", "delgado_van5", "delgado", "devon", 12, None),
    ("Order blanks for volunteer tees", "Navy tee blanks are on the shelf; confirm size breakdown.", "normal", "foodbank_shirts", "foodbank", "tomas", 2, "complete"),
    ("Permit check for Northgate monument sign", "Landlord has not returned the permit paperwork.", "normal", "northgate_monument", "northgate", "carla", 10, "block"),
    ("Clean and calibrate printer head", "Monthly maintenance after the ink restock.", "low", None, None, "tomas", 6, None),
    ("Post-install photos: Brightway detail van", "Photos for the portfolio and warranty file.", "low", "brightway_van", "brightway", "devon", -3, "complete"),
    ("Call Marcus Bell with wrap estimate", "Send the draft estimate and book a consultation.", "normal", None, "bell", "aisha", 4, None),
]

ANNOUNCEMENT = ("Welcome to the demo shop", "This is a fictional demonstration shop. Every customer, job and payment here is made up so you can explore SIGNGUY safely.")

# (employee, days ago, start hour, end hour, break minutes)
TIME_ENTRIES = [
    ("carla", 3, 8, 16.5, 30), ("carla", 2, 8, 16.5, 30), ("carla", 1, 8, 16.5, 30),
    ("devon", 3, 7.5, 15.5, 30), ("devon", 2, 7.5, 16, 30), ("devon", 1, 8, 16, 30),
    ("aisha", 3, 9, 17, 30), ("aisha", 2, 9, 17, 30), ("aisha", 1, 9, 17.5, 30),
    ("tomas", 3, 7, 15.5, 30), ("tomas", 2, 7, 15.5, 30), ("tomas", 1, 7, 15, 30),
]
