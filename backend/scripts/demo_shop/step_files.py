"""Demonstration artwork: tiny generated PNGs uploaded through the canonical file API and attached to real records.

Everything is generated locally (no downloaded or third-party assets). Files are deduplicated by content hash and
attached only when the parent does not already have a file of that name, so re-running adds nothing.
"""
from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

# key: (file name, headline, subline, background, foreground, [(parent_type, parent_key)], visibility)
ART = {
    "logo_harbor": ("harbor-coffee-logo.png", "HARBOR COFFEE", "ROASTERS - DEMO ARTWORK", "#3B2A20", "#F4E3C1", [("customer", "harbor"), ("order", "harbor_windows")], "internal"),
    "logo_delgado": ("delgado-plumbing-logo.png", "DELGADO PLUMBING", "& HEATING - DEMO ARTWORK", "#0B3C6F", "#FFFFFF", [("customer", "delgado"), ("order", "delgado_van5"), ("order", "delgado_doors")], "internal"),
    "proof_delgado_van5": ("delgado-van5-wrap-proof-v2.png", "VAN 5 WRAP PROOF", "Full wrap - proof v2 - DEMO", "#0B3C6F", "#FFD23F", [("order", "delgado_van5")], "customer_visible"),
    "logo_summit": ("summit-peak-logo.png", "SUMMIT PEAK", "LANDSCAPING - DEMO ARTWORK", "#1B5E3A", "#F2F7E8", [("customer", "summit"), ("order", "summit_pickup")], "internal"),
    "proof_summit_pickup": ("summit-pickup-partial-wrap-proof.png", "PICKUP PARTIAL WRAP", "Proof for approval - DEMO", "#1B5E3A", "#FFFFFF", [("order", "summit_pickup")], "customer_visible"),
    "logo_northgate": ("northgate-dental-logo-lowres.png", "NORTHGATE DENTAL", "low-res logo - need vector", "#5B7DB1", "#FFFFFF", [("customer", "northgate"), ("order", "northgate_wayfinding")], "internal"),
    "banner_foodbank": ("food-drive-banner-art.png", "SPRING FOOD DRIVE", "Lakeshore Community Food Bank", "#C0392B", "#FFFFFF", [("order", "foodbank_banners")], "customer_visible"),
    "tee_foodbank": ("volunteer-tee-front.png", "VOLUNTEER", "1-color front print - DEMO", "#17202A", "#F7DC6F", [("order", "foodbank_shirts")], "internal"),
    "hoodie_fireaux": ("pancake-breakfast-hoodie.png", "PANCAKE BREAKFAST", "Tri-County Fire Auxiliary", "#2E4053", "#F5B041", [("order", "fireaux_hoodies")], "internal"),
    "logo_raptors": ("riverton-raptors-logo.png", "RIVERTON RAPTORS", "YOUTH BASEBALL - DEMO", "#7D3C98", "#FDFEFE", [("customer", "raptors"), ("order", "raptors_fence")], "internal"),
    "van_before": ("brightway-van-before.png", "BEFORE", "Brightway detail van - DEMO photo", "#7F8C8D", "#FFFFFF", [("order", "brightway_van")], "internal"),
    "van_after": ("brightway-van-after.png", "AFTER", "Brightway detail van - DEMO photo", "#148F77", "#FFFFFF", [("order", "brightway_van")], "customer_visible"),
    "ironclad_wall": ("ironclad-wall-graphic.png", "IRONCLAD FITNESS", "Wall graphic - DEMO", "#1C2833", "#E74C3C", [("customer", "ironclad"), ("order", "ironclad_walls")], "internal"),
    "wedding_sign": ("raman-wedding-welcome-sign.png", "WELCOME", "Priya & Guest - DEMO", "#F5EEF8", "#6C3483", [("order", "raman_wedding")], "customer_visible"),
    "pta_logo": ("maple-ridge-pta-logo.png", "MAPLE RIDGE", "ELEMENTARY PTA - DEMO", "#1F618D", "#F9E79F", [("customer", "maple_pta")], "internal"),
    "boosters_logo": ("westfield-boosters-logo.png", "WESTFIELD WARRIORS", "ATHLETICS BOOSTERS - DEMO", "#7B241C", "#F7DC6F", [("customer", "boosters")], "internal"),
    "ironclad_5k_logo": ("ironclad-5k-logo.png", "IRONCLAD 5K", "Community run - DEMO", "#1C2833", "#58D68D", [("customer", "ironclad")], "internal"),
    "harvest_logo": ("cedar-hollow-harvest-logo.png", "HARVEST FESTIVAL", "Cedar Hollow Brewing - DEMO", "#784212", "#FAD7A0", [("customer", "cedarhollow")], "internal"),
}


def render(headline: str, sub: str, bg: str, fg: str) -> bytes:
    img = Image.new("RGB", (800, 480), bg)
    draw = ImageDraw.Draw(img)
    draw.rectangle([24, 24, 775, 455], outline=fg, width=6)
    big, small = ImageFont.load_default(size=56), ImageFont.load_default(size=26)
    draw.text((400, 210), headline, fill=fg, font=big, anchor="mm")
    draw.text((400, 290), sub, fill=fg, font=small, anchor="mm")
    draw.text((400, 430), "SIGNGUY DEMO SHOP - fictional artwork", fill=fg, font=ImageFont.load_default(size=16), anchor="mm")
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


async def upload(ctx, key: str, parent_type: str | None = None, parent_id: str | None = None) -> dict:
    """Upload (deduplicated) one demo art file; attach it to a parent when none of that name is attached yet."""
    name, head, sub, bg, fg, _parents, visibility = ART[key]
    if parent_type and parent_id:
        attached = await ctx.api.items("/files", parent_type=parent_type, parent_id=parent_id, limit=100)
        if any(f["original_filename"] == name for f in attached):
            ctx.note("files", False)
            return next(f for f in attached if f["original_filename"] == name)
    data = {"visibility": visibility}
    if parent_type and parent_id:
        data.update(parent_type=parent_type, parent_id=parent_id)
    body = await ctx.api.call("POST", "/files/upload", files={"file": (name, render(head, sub, bg, fg), "image/png")}, data=data)
    ctx.note("files", True)
    return body["file"]


async def artwork(ctx) -> None:
    for key, (_n, _h, _s, _b, _f, parents, _v) in ART.items():
        for parent_type, parent_key in parents:
            parent_id = ctx.ids[f"{parent_type}:{parent_key}"]
            f = await upload(ctx, key, parent_type, parent_id)
            ctx.ids[f"file:{key}"] = f["id"]
