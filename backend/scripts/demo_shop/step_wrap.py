"""Wrap Lab: demonstration vehicles and projects at different stages of the real project lifecycle."""
from __future__ import annotations

from scripts.demo_shop import step_files
from scripts.demo_shop.step_ops import at, calendar_rows
from scripts.demo_shop.step_work import day

STATUS_ORDER = [
    "lead_intake", "vehicle_recorded", "measurement_planning", "estimate_ready", "quote_linked", "contract_deposit_pending",
    "pre_install_ready", "pre_install_signed", "design_in_progress", "proof_ready", "proof_approved", "panel_plan_ready",
    "production_ready", "install_scheduled", "installing", "completion_packet_ready", "completed", "warranty_active",
]

# (key, customer, vehicle fields)
VEHICLES = [
    ("van5", "delgado", dict(year="2022", make="Ford", model="Transit 250", trim="High Roof 148in WB", vehicle_type="van", color="White", unit_number="Van 5",
                             license_plate="DEMO-005", vin="1FTBR0DEMO0000005", requested_coverage="Full wrap", target_install_at=None,
                             measured_wrap_areas=[{"name": "Driver side", "width_inches": 190, "height_inches": 72}, {"name": "Passenger side", "width_inches": 190, "height_inches": 72},
                                                  {"name": "Rear doors", "width_inches": 62, "height_inches": 66}, {"name": "Roof", "width_inches": 150, "height_inches": 60}],
                             customer_instructions="Keep brand blue consistent with the other vans.")),
    ("pickup", "summit", dict(year="2021", make="Ram", model="1500 Crew Cab", trim="Big Horn", vehicle_type="pickup", color="Silver", unit_number="Truck 2",
                              license_plate="DEMO-102", vin="1C6SRFFTDEMO000102", requested_coverage="Partial wrap with tailgate logo",
                              measured_wrap_areas=[{"name": "Driver side lower", "width_inches": 150, "height_inches": 30}, {"name": "Passenger side lower", "width_inches": 150, "height_inches": 30},
                                                   {"name": "Tailgate", "width_inches": 62, "height_inches": 22}])),
    ("sprinter", "brightway", dict(year="2020", make="Mercedes-Benz", model="Sprinter 2500", trim="144in WB", vehicle_type="sprinter_van", color="White", unit_number="Detail Van",
                                   license_plate="DEMO-208", vin="WD3PE7CDEMO0000208", requested_coverage="Partial graphics",
                                   measured_wrap_areas=[{"name": "Driver side panel", "width_inches": 120, "height_inches": 54}, {"name": "Passenger side panel", "width_inches": 120, "height_inches": 54},
                                                        {"name": "Rear doors", "width_inches": 60, "height_inches": 60}])),
    ("van3", "delgado", dict(year="2019", make="Ford", model="Transit Connect", trim="XLT", vehicle_type="van", color="White", unit_number="Van 3",
                             license_plate="DEMO-003", vin="NM0LS7EDEMO0000003", requested_coverage="Door lettering",
                             measured_wrap_areas=[{"name": "Driver door", "width_inches": 40, "height_inches": 18}, {"name": "Passenger door", "width_inches": 40, "height_inches": 18}])),
    ("foodtruck", "bell", dict(year="2018", make="Isuzu", model="NPR", trim="Box truck", vehicle_type="box_truck", color="White", unit_number="Truck",
                               requested_coverage="Full wrap (estimate only)", internal_notes="Lead: vehicle not yet inspected.")),
]

PANELS_FULL = [{"name": n, "width_inches": w, "height_inches": h, "selected": True} for n, w, h in
               [("Driver side", 190, 72), ("Passenger side", 190, 72), ("Rear doors", 62, 66), ("Roof", 150, 60), ("Hood", 60, 50)]]
PANELS_PARTIAL = [{"name": n, "width_inches": w, "height_inches": h, "selected": True} for n, w, h in
                  [("Driver side lower", 150, 30), ("Passenger side lower", 150, 30), ("Tailgate", 62, 22)]]
PANELS_BRIGHTWAY = [{"name": n, "width_inches": w, "height_inches": h, "selected": True} for n, w, h in
                    [("Driver side panel", 120, 54), ("Passenger side panel", 120, 54), ("Rear doors", 60, 60)]]

PRE_INSPECTION = dict(
    inspection_type="pre_install", required_views=["driver_side", "passenger_side", "front", "rear", "roof"],
    damage_items=[{"type": "scratch", "location": "Rear bumper", "severity": "minor", "note": "Pre-existing, documented before install"}],
    surface_conditions=[{"area": "Body panels", "condition": "clean", "note": "Washed and degreased before inspection"}],
)


def scene(logo_file_id: str | None, headline: str) -> dict:
    layers = [{"id": "tpl", "type": "vehicle_template", "name": "Vehicle template", "locked": True},
              {"id": "bg", "type": "background", "name": "Brand background"},
              {"id": "txt", "type": "text", "name": headline, "text": headline}]
    if logo_file_id:
        layers.append({"id": "logo", "type": "logo_asset", "name": "Customer logo", "source_file_id": logo_file_id, "locked": True})
    return {"status": "in_progress", "vehicle_template_key": "default", "layers": layers, "notes": "Demonstration design scene."}


async def _advance(api, project_id: str, current: str, target: str) -> str:
    for status in STATUS_ORDER[STATUS_ORDER.index(current) + 1:STATUS_ORDER.index(target) + 1]:
        await api.post(f"/wrap-lab/projects/{project_id}/status", {"status": status})
        current = status
    return current


async def _project(ctx, existing: dict, key: str, body: dict, target: str):
    api = ctx.api
    fresh = body["project_name"] not in existing
    project = existing.get(body["project_name"])
    if fresh:
        project = await api.post("/wrap-lab/projects", body)
        existing[body["project_name"]] = project
        ctx.note("wrap_projects", True)
    else:
        ctx.note("wrap_projects", False)
    ctx.ids[f"wrap:{key}"] = project["id"]
    return project, fresh


async def wrap_lab(ctx) -> None:
    api = ctx.api
    vehicles = {(v.get("unit_number") or "", v["model"]): v for v in await api.items("/wrap-lab/vehicles")}
    vehicle_ids: dict[str, str] = {}
    for key, customer, fields in VEHICLES:
        have = vehicles.get((fields.get("unit_number") or "", fields["model"]))
        if have is None:
            have = await api.post("/wrap-lab/vehicles", {"customer_id": ctx.ids[f"customer:{customer}"], **fields})
            ctx.note("wrap_vehicles", True)
        else:
            ctx.note("wrap_vehicles", False)
        vehicle_ids[key] = have["id"]
    projects = {p["project_name"]: p for p in await api.items("/wrap-lab/projects")}

    def order_links(order_key: str, with_item: bool = True) -> dict:
        links = {"order_id": ctx.ids[f"order:{order_key}"], "work_order_id": ctx.ids[f"wo:{order_key}"]}
        return links

    async def first_item(order_key: str) -> str:
        return (await api.get(f"/orders/{ctx.ids[f'order:{order_key}']}"))["items"][0]["id"]

    # 1. Delgado Van 5 - full wrap in design, pre-install inspection awaiting customer signature
    p, fresh = await _project(ctx, projects, "van5", {
        "customer_id": ctx.ids["customer:delgado"], "vehicle_id": vehicle_ids["van5"], **order_links("delgado_van5"),
        "order_item_id": await first_item("delgado_van5"), "project_name": "Delgado Van 5 - full wrap", "project_type": "full_wrap",
        "coverage_summary": "Full wrap, all panels, roof included", "estimate_total_cents": 485000, "deposit_required_cents": 242500,
        "material_estimate_cents": 118000, "labor_estimate_cents": 120000,
        "assigned_user_ids": [ctx.ids["user:aisha"], ctx.ids["user:devon"]], "due_at": at(21, 17)}, "design_in_progress")
    if fresh:
        await api.post(f"/wrap-lab/projects/{p['id']}/coverage-plans", {"coverage_level": "full_wrap", "panels": PANELS_FULL, "waste_percent": 15, "status": "measured"})
        await api.post(f"/wrap-lab/projects/{p['id']}/inspections", {**PRE_INSPECTION, "status": "ready_for_signature",
                       "before_photo_file_ids": [], "notes": "Waiting for Marco Delgado to sign the pre-install inspection."})
        await api.post(f"/wrap-lab/projects/{p['id']}/design-scenes", scene(ctx.ids.get("file:logo_delgado"), "DELGADO PLUMBING & HEATING"))
        await _advance(api, p["id"], "lead_intake", "design_in_progress")

    # 2. Summit Peak pickup - partial wrap, signed pre-install inspection, proof out for approval
    p, fresh = await _project(ctx, projects, "pickup", {
        "customer_id": ctx.ids["customer:summit"], "vehicle_id": vehicle_ids["pickup"], **order_links("summit_pickup"),
        "order_item_id": await first_item("summit_pickup"), "project_name": "Summit Peak pickup - partial wrap", "project_type": "partial_wrap",
        "coverage_summary": "Lower side panels and tailgate", "estimate_total_cents": 189000, "deposit_required_cents": 94500,
        "material_estimate_cents": 41000, "labor_estimate_cents": 52000, "assigned_user_ids": [ctx.ids["user:aisha"]], "due_at": at(18, 17)}, "proof_ready")
    if fresh:
        await api.post(f"/wrap-lab/projects/{p['id']}/coverage-plans", {"coverage_level": "partial_wrap", "panels": PANELS_PARTIAL, "waste_percent": 15, "status": "designed"})
        insp = await api.post(f"/wrap-lab/projects/{p['id']}/inspections", {**PRE_INSPECTION, "status": "ready_for_signature", "notes": "Customer signed at drop-off."})
        await api.post(f"/wrap-lab/inspections/{insp['id']}/acknowledgement", {"signer_name": "Tara Nguyen", "signer_email": "tara@summitpeak.example.com",
                       "signature_type": "typed", "signature_data": "Tara Nguyen"})
        await api.post(f"/wrap-lab/projects/{p['id']}/design-scenes", {**scene(ctx.ids.get("file:logo_summit"), "SUMMIT PEAK LANDSCAPING"), "status": "proof_ready"})
        await _advance(api, p["id"], "lead_intake", "proof_ready")

    # 3. Brightway detail van - the full lifecycle, completed with an active warranty
    p, fresh = await _project(ctx, projects, "sprinter", {
        "customer_id": ctx.ids["customer:brightway"], "vehicle_id": vehicle_ids["sprinter"], **order_links("brightway_van"),
        "order_item_id": await first_item("brightway_van"), "project_name": "Brightway detail van - partial graphics", "project_type": "partial_wrap",
        "coverage_summary": "Side panels and rear doors", "estimate_total_cents": 142000, "deposit_required_cents": 71000,
        "material_estimate_cents": 36000, "labor_estimate_cents": 48000, "assigned_user_ids": [ctx.ids["user:aisha"], ctx.ids["user:devon"]], "due_at": at(-8, 17)}, "warranty_active")
    if fresh:
        before, after = ctx.ids["file:van_before"], ctx.ids["file:van_after"]
        await api.post(f"/wrap-lab/projects/{p['id']}/coverage-plans", {"coverage_level": "partial_wrap", "panels": PANELS_BRIGHTWAY, "waste_percent": 15, "status": "wrapped"})
        pre = await api.post(f"/wrap-lab/projects/{p['id']}/inspections", {**PRE_INSPECTION, "status": "ready_for_signature", "before_photo_file_ids": [before]})
        await api.post(f"/wrap-lab/inspections/{pre['id']}/acknowledgement", {"signer_name": "Kevin Park", "signer_email": "kevin@brightwaydetail.example.com",
                       "signature_type": "typed", "signature_data": "Kevin Park"})
        await api.post(f"/wrap-lab/projects/{p['id']}/design-scenes", {**scene(None, "BRIGHTWAY AUTO DETAILING"), "status": "approved"})
        await api.post(f"/wrap-lab/projects/{p['id']}/panel-plans", {"status": "exported", "printer_max_width_inches": 54, "overlap_inches": 0.5, "bleed_inches": 1,
                       "panels": [{"name": n["name"], "width_inches": min(n["width_inches"], 54), "height_inches": n["height_inches"]} for n in PANELS_BRIGHTWAY],
                       "export_formats": ["pdf"], "material_usage_square_feet": 52, "material_cost_cents": 36000, "labor_cost_cents": 48000})
        for packet in ("pre_install", "work_order", "completion", "warranty_aftercare"):
            await api.post(f"/wrap-lab/projects/{p['id']}/packets", {"packet_type": packet, "notes": "Generated for the demonstration shop."})
        await api.post(f"/wrap-lab/projects/{p['id']}/schedules", {"schedule_type": "install", "status": "completed", "title": "Install: Brightway detail van",
                       "start_at": at(-10, 8), "end_at": at(-10, 16), "assigned_user_ids": [ctx.ids["user:devon"]], "location": "Shop garage"})
        await api.post(f"/wrap-lab/projects/{p['id']}/installation-records", {
            "status": "completed", "installer_user_ids": [ctx.ids["user:devon"]], "crew_names": ["Devon Pike", "Tomas Reyes"],
            "actual_start_at": at(-10, 8), "actual_end_at": at(-10, 15.5), "location": "Shop garage",
            "preparation_checklist": [{"item": "Wash and degrease", "completed": True}, {"item": "Surface inspection", "completed": True}],
            "installation_checklist": [{"item": "Panels aligned", "completed": True}, {"item": "Post-heat edges", "completed": True}],
            "completion_photo_file_ids": [after], "quality_notes": "No lifting or bubbles at 24-hour check."})
        await api.post(f"/wrap-lab/projects/{p['id']}/inspections", {"inspection_type": "completion", "status": "completed", "after_photo_file_ids": [after],
                       "notes": "Completion walk-around with the owner. No new damage."})
        await api.post(f"/wrap-lab/projects/{p['id']}/warranties", {"status": "active", "starts_at": day(-9), "expires_at": day(365 * 3),
                       "coverage_terms": ["Material and installation defects for 3 years"], "care_instructions": ["Hand wash only for 30 days", "No pressure washing near edges"],
                       "warranty_value_cents": 142000})
        await _advance(api, p["id"], "lead_intake", "warranty_active")

    # 4. Delgado Van 3 - door lettering with the install on the calendar
    p, fresh = await _project(ctx, projects, "van3", {
        "customer_id": ctx.ids["customer:delgado"], "vehicle_id": vehicle_ids["van3"], "order_id": ctx.ids["order:delgado_doors"],
        "work_order_id": ctx.ids["wo:delgado_doors"], "project_name": "Delgado Van 3 - door lettering", "project_type": "lettering",
        "coverage_summary": "Cut vinyl door lettering", "estimate_total_cents": 22500, "assigned_user_ids": [ctx.ids["user:devon"]], "due_at": at(3, 17)}, "install_scheduled")
    if fresh:
        await api.post(f"/wrap-lab/projects/{p['id']}/coverage-plans", {"coverage_level": "lettering", "status": "designed",
                       "panels": [{"name": "Driver door", "width_inches": 40, "height_inches": 18, "selected": True}, {"name": "Passenger door", "width_inches": 40, "height_inches": 18, "selected": True}]})
        await api.post(f"/wrap-lab/projects/{p['id']}/schedules", {"schedule_type": "install", "status": "scheduled", "title": "Install: Delgado Van 3 door lettering",
                       "start_at": at(3, 8), "end_at": at(3, 12), "assigned_user_ids": [ctx.ids["user:devon"]], "location": "Delgado Plumbing & Heating shop",
                       "calendar_event_id": next(r["id"] for r in await calendar_rows(ctx) if r["title"] == "Install: Delgado fleet door lettering")})
        await _advance(api, p["id"], "lead_intake", "install_scheduled")

    # 5. Marcus Bell - food truck lead, vehicle recorded, no order yet
    p, fresh = await _project(ctx, projects, "foodtruck", {
        "customer_id": ctx.ids["customer:bell"], "vehicle_id": vehicle_ids["foodtruck"], "project_name": "Bell food truck - wrap lead", "project_type": "full_wrap",
        "coverage_summary": "Full wrap estimate requested", "estimate_total_cents": 380000}, "vehicle_recorded")
    if fresh:
        await _advance(api, p["id"], "lead_intake", "vehicle_recorded")
