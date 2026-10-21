"""Fictional shop profile, team, supplier, material and equipment content for SIGNGUY DEMO SHOP.

Prices are demonstration values (integer cents unless a comment says dollars).
"""
from __future__ import annotations

COMPANY_PROFILE = {
    "shop_name": "SIGNGUY DEMO SHOP", "legal_name": "SignGuy Demo Shop LLC", "phone": "555-0100",
    "email": "hello@signguy-demo.example.com", "website": "https://signguy-demo.example.com",
    "address": "100 Commerce Way, Fairhaven, OH 44800", "timezone": "America/New_York",
}
BRANDING = {"brand_color": "#E4572E"}

# (key, full name, email, role label, hourly cents, hire date)
STAFF = [
    ("carla", "Carla Mendes", "carla.mendes@signguy-demo.example.com", "Production Manager", 3200, "2022-03-14"),
    ("devon", "Devon Pike", "devon.pike@signguy-demo.example.com", "Lead Installer", 3000, "2023-06-05"),
    ("aisha", "Aisha Grant", "aisha.grant@signguy-demo.example.com", "Graphic Designer", 2800, "2023-01-23"),
    ("tomas", "Tomas Reyes", "tomas.reyes@signguy-demo.example.com", "Print & Production Technician", 2300, "2024-02-12"),
]

VENDORS = [
    ("Gulf Coast Sign Supply", "Vinyl, banner stock, laminates, rigid substrates", ["vinyl", "banner", "rigid", "laminate"], "orders@gulfcoastsupply.example.com", "555-0140"),
    ("Midwest Print Consumables", "Inks, tape, tools and hardware", ["ink", "hardware", "consumables"], "sales@midwestprint.example.com", "555-0141"),
    ("Apparel Direct Blanks", "Blank tees, hoodies and performance wear", ["apparel"], "wholesale@appareldirect.example.com", "555-0142"),
]
LOCATIONS = [("Main Shop Storage", "warehouse"), ("Print Room Rack", "production"), ("Install Van 1", "vehicle")]

# key: (name, sku, category, unit, cost_cents, extra fields, [(location, qty)], reorder_point, reorder_qty)
MATERIALS = {
    "cast_white": ("Cast Vinyl - Gloss White 54in x 50yd", "VIN-CAST-GW54", "vinyl", "roll", 28500,
                   {"roll_width_inches": 54, "roll_length_feet": 150}, [("Main Shop Storage", 3), ("Print Room Rack", 1)], 2, 4),
    "print_vinyl": ("Printable Calendared Vinyl 54in x 150ft", "VIN-PRT-54", "printable_media", "roll", 14200,
                    {"roll_width_inches": 54, "roll_length_feet": 150}, [("Print Room Rack", 2), ("Main Shop Storage", 2)], 2, 4),
    "cut_black": ("Cut Vinyl - Black 24in x 50yd", "VIN-CUT-BK24", "vinyl", "roll", 5800,
                  {"roll_width_inches": 24, "roll_length_feet": 150}, [("Main Shop Storage", 4)], 2, 4),
    "cut_white": ("Cut Vinyl - White 24in x 50yd", "VIN-CUT-WH24", "vinyl", "roll", 5800,
                  {"roll_width_inches": 24, "roll_length_feet": 150}, [("Main Shop Storage", 3)], 2, 4),
    "cut_red": ("Cut Vinyl - Red 24in x 50yd", "VIN-CUT-RD24", "vinyl", "roll", 6100,
                {"roll_width_inches": 24, "roll_length_feet": 150}, [("Main Shop Storage", 1)], 2, 3),
    "reflective": ("Reflective Sheeting - White 24in x 50yd", "VIN-REF-WH24", "vinyl", "roll", 21500,
                   {"roll_width_inches": 24, "roll_length_feet": 150}, [("Main Shop Storage", 1)], 1, 2),
    "banner_13oz": ("Banner Material 13oz Scrim Vinyl 54in x 164ft", "BAN-13-54", "banner", "roll", 9200,
                    {"roll_width_inches": 54, "roll_length_feet": 164}, [("Print Room Rack", 3)], 2, 3),
    "laminate": ("Gloss Overlaminate 54in x 150ft", "LAM-GL-54", "laminate", "roll", 9600,
                 {"roll_width_inches": 54, "roll_length_feet": 150}, [("Print Room Rack", 2)], 2, 3),
    "transfer_tape": ("Application Tape 48in x 300ft", "TAP-APP-48", "application_tape", "roll", 8400,
                      {"roll_width_inches": 48, "roll_length_feet": 300}, [("Main Shop Storage", 2)], 1, 2),
    "acm_3mm": ("Aluminum Composite Panel 3mm 48x96 White", "RIG-ACM3-4896", "substrate", "sheet", 6400,
                {"sheet_width_inches": 48, "sheet_height_inches": 96}, [("Main Shop Storage", 12)], 6, 12),
    "coro_4mm": ("Corrugated Plastic 4mm 48x96 White", "RIG-COR4-4896", "substrate", "sheet", 1450,
                 {"sheet_width_inches": 48, "sheet_height_inches": 96}, [("Main Shop Storage", 40)], 20, 40),
    "pvc_6mm": ("PVC Foam Board 6mm 48x96 White", "RIG-PVC6-4896", "substrate", "sheet", 4800,
                {"sheet_width_inches": 48, "sheet_height_inches": 96}, [("Main Shop Storage", 8)], 4, 8),
    "tee_navy": ("Cotton T-Shirt Blank - Navy (Adult)", "APP-TEE-NVY", "apparel", "each", 380, {}, [("Main Shop Storage", 96)], 48, 144),
    "tee_red": ("Performance T-Shirt Blank - Red (Adult)", "APP-PTEE-RED", "apparel", "each", 560, {}, [("Main Shop Storage", 72)], 36, 144),
    "hoodie": ("Fleece Hoodie Blank - Charcoal (Adult)", "APP-HOOD-CHR", "apparel", "each", 1450, {}, [("Main Shop Storage", 30)], 24, 72),
    "grommets": ("Brass Grommets #2 (box of 500)", "HW-GROM-500", "hardware", "package", 1800, {}, [("Main Shop Storage", 6)], 3, 6),
    "hstakes": ("H-Stakes 10x30 Wire (pack of 25)", "HW-HSTK-25", "hardware", "package", 4800, {}, [("Main Shop Storage", 5)], 3, 6),
    "ink_black": ("Eco-Solvent Ink Cartridge - Black 440ml", "INK-ES-BK", "ink", "each", 9800, {}, [("Print Room Rack", 4)], 2, 4),
    "ink_cyan": ("Eco-Solvent Ink Cartridge - Cyan 440ml", "INK-ES-CY", "ink", "each", 9800, {}, [("Print Room Rack", 3)], 2, 4),
    "ink_magenta": ("Eco-Solvent Ink Cartridge - Magenta 440ml", "INK-ES-MG", "ink", "each", 9800, {}, [("Print Room Rack", 1)], 2, 4),
    "ink_yellow": ("Eco-Solvent Ink Cartridge - Yellow 440ml", "INK-ES-YL", "ink", "each", 9800, {}, [("Print Room Rack", 3)], 2, 4),
}

# material key -> pricing profile (the Pricing Foundation API is dollar-based)
PRICING_PROFILES = {
    "banner_13oz": dict(pricing_unit="per_sqft", normalized_cost_basis=1.03, waste_percent=10, default_markup_multiplier=3.0, suggested_sell_rate=5.5, minimum_sell_amount=45.0, category_applicability=["banners"]),
    "print_vinyl": dict(pricing_unit="per_sqft", normalized_cost_basis=1.82, waste_percent=10, default_markup_multiplier=3.0, suggested_sell_rate=8.5, minimum_sell_amount=35.0, category_applicability=["digital_print", "vehicle_graphics"]),
    "cast_white": dict(pricing_unit="per_sqft", normalized_cost_basis=3.65, waste_percent=12, default_markup_multiplier=2.8, suggested_sell_rate=14.0, minimum_sell_amount=75.0, category_applicability=["vehicle_graphics"]),
    "cut_black": dict(pricing_unit="per_sqft", normalized_cost_basis=2.9, waste_percent=15, default_markup_multiplier=3.5, suggested_sell_rate=11.0, minimum_sell_amount=30.0, category_applicability=["cut_vinyl"]),
    "acm_3mm": dict(pricing_unit="per_sqft", normalized_cost_basis=2.0, waste_percent=8, default_markup_multiplier=3.0, suggested_sell_rate=12.0, minimum_sell_amount=60.0, category_applicability=["rigid_signs"]),
    "coro_4mm": dict(pricing_unit="per_sqft", normalized_cost_basis=0.45, waste_percent=8, default_markup_multiplier=3.5, suggested_sell_rate=4.5, minimum_sell_amount=20.0, category_applicability=["rigid_signs"]),
}

# (key, name, charge_type, amount dollars, percent, category applicability)
PRICING_COMPONENTS = [
    ("rush_fee", "Rush Fee (24-hour)", "rush_charge", None, 25.0, ["banners", "rigid_signs", "cut_vinyl", "digital_print"]),
    ("file_cleanup", "Artwork Cleanup", "file_cleanup", 20.0, None, ["banners", "rigid_signs", "cut_vinyl", "digital_print", "vehicle_graphics"]),
    ("grommets_hems", "Hems & Grommets", "other", 12.0, None, ["banners"]),
    ("install_minimum", "Installation Minimum", "install_minimum", 150.0, None, ["vehicle_graphics", "rigid_signs"]),
]

# (name, category, manufacturer, model, serial, location, safety sensitive)
EQUIPMENT = [
    ("Large-Format Eco-Solvent Printer 64in", "printer", "ProPrint", "ES-64", "PP-ES64-0001", "Print Room", True),
    ("Contour Cutter / Plotter 54in", "cutter", "CutWorks", "CW-54", "CW54-1177", "Print Room", False),
    ("Roll Laminator 55in", "laminator", "PressMark", "RL-55", "RL55-0420", "Print Room", False),
    ("Heat Press 16x20 Clamshell", "heat_press", "HeatPro", "HP-1620", "HP1620-3302", "Apparel Bench", True),
    ("CNC Router Table 4x8", "specialty_tool", "RouteMaster", "RM-4896", "RM4896-0088", "Rigid Shop", True),
    ("Install Van 1 (Ford Transit)", "vehicle", "Ford", "Transit 250", "VAN-0001", "Garage", False),
]
