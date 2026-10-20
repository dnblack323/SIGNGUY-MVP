"""Fictional demonstration content for SIGNGUY DEMO SHOP.

Every person, business, email (``example.com``) and phone (``555-01xx``) is invented. Money is
integer cents. Keys are stable so a re-run finds the same records.
"""
from __future__ import annotations

_CITY = {"city": "Fairhaven", "state": "OH", "country": "US"}


def _c(key, name, ctype, email, phone, street, zip_, contact, role, notes, company=None, lifecycle="active"):
    payload = {
        "name": name, "customer_type": ctype, "lifecycle_status": lifecycle, "email": email, "phone": phone,
        "address_line1": street, "postal_code": zip_, **_CITY, "notes": notes,
        "contacts": [{"name": contact[0], "email": contact[1], "phone": phone, "role": role, "title": contact[2], "is_primary": True}],
    }
    if company:
        payload["company"] = company
    return key, payload


CUSTOMERS = dict([
    _c("maple_pta", "Maple Ridge Elementary PTA", "organization", "pta@mapleridge.example.com", "555-0101", "410 School St", "44801",
       ("Dana Whitaker", "dana.whitaker@mapleridge.example.com", "PTA President"), "primary",
       "Annual spirit-wear fundraiser every fall. Tax exempt. Prefers email; approves artwork through the PTA board."),
    _c("raptors", "Riverton Raptors Youth Baseball", "organization", "board@rivertonraptors.example.com", "555-0102", "88 Diamond Ave", "44802",
       ("Luis Ortega", "luis.ortega@rivertonraptors.example.com", "League Treasurer"), "billing",
       "Team banners, field signage and uniforms each spring. Pays after sponsor checks clear."),
    _c("harbor", "Harbor Coffee Roasters", "business", "owner@harborcoffee.example.com", "555-0103", "12 Dockside Rd", "44803",
       ("Nina Castellano", "nina@harborcoffee.example.com", "Owner"), "primary",
       "Repeat customer since last year. Seasonal window graphics and sidewalk A-frames.", company="Harbor Coffee Roasters LLC"),
    _c("delgado", "Delgado Plumbing & Heating", "business", "office@delgadoplumbing.example.com", "555-0104", "2250 Industrial Pkwy", "44804",
       ("Marco Delgado", "marco@delgadoplumbing.example.com", "Owner"), "primary",
       "Fleet of 6 vans. Wants consistent branding across every vehicle. Net-15 terms.", company="Delgado Plumbing & Heating Inc."),
    _c("summit", "Summit Peak Landscaping", "business", "hello@summitpeak.example.com", "555-0105", "719 Orchard Ln", "44805",
       ("Tara Nguyen", "tara@summitpeak.example.com", "Operations Manager"), "primary",
       "Two pickups and a trailer. Likes partial wraps and cut-vinyl lettering.", company="Summit Peak Landscaping LLC"),
    _c("northgate", "Northgate Dental Group", "business", "frontdesk@northgatedental.example.com", "555-0106", "301 Northgate Plz", "44806",
       ("Dr. Alan Brooks", "abrooks@northgatedental.example.com", "Practice Owner"), "approval",
       "New second location opening. Needs ADA-compliant interior wayfinding and an exterior monument sign.", company="Northgate Dental Group PC"),
    _c("foodbank", "Lakeshore Community Food Bank", "organization", "events@lakeshorefoodbank.example.com", "555-0107", "55 Lakeshore Dr", "44807",
       ("Rosa Mendez", "rosa@lakeshorefoodbank.example.com", "Events Coordinator"), "primary",
       "Nonprofit; discount approved by owner. Two big events a year: spring drive and holiday drive."),
    _c("fireaux", "Tri-County Fire Auxiliary", "organization", "auxiliary@tricountyfire.example.com", "555-0108", "9 Station Rd", "44808",
       ("Pat Sullivan", "pat.sullivan@tricountyfire.example.com", "Auxiliary Chair"), "primary",
       "Volunteer fire auxiliary. Orders t-shirts and hoodies for the annual pancake breakfast."),
    _c("brightway", "Brightway Auto Detailing", "business", "book@brightwaydetail.example.com", "555-0109", "640 Garage Way", "44809",
       ("Kevin Park", "kevin@brightwaydetail.example.com", "Owner"), "primary",
       "Mobile detailing van plus shop signage. Pays by card at pickup.", company="Brightway Auto Detailing"),
    _c("patel", "Patel Family Bakery", "business", "orders@patelbakery.example.com", "555-0110", "17 Main St", "44810",
       ("Anita Patel", "anita@patelbakery.example.com", "Co-owner"), "primary",
       "Storefront lettering and a rotating menu board. Needs fast turnaround before holidays.", company="Patel Family Bakery LLC"),
    _c("whitfield", "Jordan Whitfield", "individual", "jordan.whitfield@example.com", "555-0111", "31 Elm Ct", "44811",
       ("Jordan Whitfield", "jordan.whitfield@example.com", None), "primary",
       "Personal vehicle decals and a memorial window decal for a family member."),
    _c("raman", "Priya Raman", "individual", "priya.raman@example.com", "555-0112", "902 Willow Bend", "44812",
       ("Priya Raman", "priya.raman@example.com", None), "primary",
       "Wedding welcome sign and seating chart board. Event is in six weeks."),
    _c("boosters", "Westfield High Athletics Boosters", "organization", "boosters@westfieldhigh.example.com", "555-0113", "1 Warrior Way", "44813",
       ("Coach Brenda Hayes", "bhayes@westfieldhigh.example.com", "Boosters Liaison"), "primary",
       "Sports team apparel for 9 teams. Runs a team webstore each season."),
    _c("ironclad", "Ironclad Fitness Studio", "business", "info@ironcladfit.example.com", "555-0114", "480 Foundry St", "44814",
       ("Mia Torres", "mia@ironcladfit.example.com", "Studio Manager"), "primary",
       "Wall graphics, floor decals and branded merchandise for their community 5K.", company="Ironclad Fitness LLC"),
    _c("cedarhollow", "Cedar Hollow Brewing Co.", "business", "taproom@cedarhollow.example.com", "555-0115", "73 Cooper Alley", "44815",
       ("Sam Whitlock", "sam@cedarhollow.example.com", "Marketing Lead"), "primary",
       "Annual harvest festival with merchandise. Banners and sandwich boards each season.", company="Cedar Hollow Brewing Co."),
    _c("bell", "Marcus Bell", "individual", "marcus.bell@example.com", "555-0116", "5 Birch Lane", "44816",
       ("Marcus Bell", "marcus.bell@example.com", None), "primary",
       "Asked about a food-truck wrap last week. No quote yet.", lifecycle="lead"),
    _c("oakline", "Oakline Realty", "business", "agents@oaklinerealty.example.com", "555-0117", "200 Oakline Blvd", "44817",
       ("Gwen Ellis", "gwen@oaklinerealty.example.com", "Office Manager"), "primary",
       "Real-estate yard signs and rider panels in bulk; reorders every quarter.", company="Oakline Realty Group"),
    _c("stbrigid", "St. Brigid Parish Hall", "organization", "hall@stbrigid.example.com", "555-0118", "300 Church St", "44818",
       ("Fr. Tom Reilly", "office@stbrigid.example.com", "Pastor"), "approval",
       "Seasonal banners for the fall festival and Christmas bazaar."),
])
