import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const GARMENT_TYPES = [
  ["short_sleeve_tee", "Short Sleeve Tee"], ["long_sleeve_tee", "Long Sleeve Tee"],
  ["crewneck_sweatshirt", "Crewneck Sweatshirt"], ["hoodie", "Hoodie"], ["polo", "Polo"],
  ["standard_cap", "Standard Cap"], ["premium_cap", "Premium Cap"], ["visor", "Visor"],
];
const HAT_TYPES = new Set(["standard_cap", "premium_cap", "visor"]);
const BRANDS_BY_GARMENT = {
  short_sleeve_tee: [["gildan_5000", "Gildan 5000"], ["bella_3001", "Bella + Canvas 3001"]],
  long_sleeve_tee: [["gildan_2400", "Gildan 2400"], ["bella_3501", "Bella + Canvas 3501"]],
  crewneck_sweatshirt: [["gildan_18000", "Gildan 18000"], ["bella_3901", "Bella + Canvas 3901"]],
  hoodie: [["gildan_18500", "Gildan 18500"], ["bella_3719", "Bella + Canvas 3719"]],
  polo: [["gildan_8800", "Gildan 8800"], ["bella_3415", "Bella + Canvas 3415"]],
};
const DECORATION_METHODS = [
  ["htv", "HTV"], ["screen_print_transfer", "Screen Print Transfer"], ["dtf_transfer", "DTF Transfer"],
  ["direct_screen_print", "Direct Screen Print"], ["embroidery", "Embroidery"], ["dtg", "DTG"],
  ["patch_emblem", "Patch / Emblem"], ["sublimation", "Sublimation"], ["specialty_custom", "Specialty / Custom"],
];
const SIZE_KEYS = ["XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"];

const VEHICLE_TYPES = [
  ["sedan", "Sedan"], ["suv", "SUV"], ["pickup", "Pickup"], ["mini_van", "Mini Van (provisional estimate)"],
  ["cargo_van", "Cargo Van"], ["sprinter_van", "Sprinter Van"], ["box_truck_12", "12 ft Box Truck"],
  ["box_truck_16", "16 ft Box Truck"], ["box_truck_24", "24 ft Box Truck (provisional estimate)"],
  ["trailer", "Trailer"], ["semi", "Semi Truck (provisional estimate)"], ["other", "Custom / Other Vehicle"],
];
const VEHICLE_COVERAGE_TYPES = [
  ["spot", "Spot Graphics (~15%)"], ["partial", "Partial Wrap (~40%)"], ["half", "Half Wrap (~55%)"],
  ["full", "Full Wrap (100%)"], ["custom", "Custom Percentage"],
];
const VEHICLE_MATERIALS = [
  ["standard_calendared_vinyl", "Standard Calendared Vinyl"], ["premium_cast_vinyl", "Premium Cast Vinyl"],
  ["wrap_cast_film", "Wrap Cast Film"], ["reflective_vinyl", "Reflective Vinyl"],
  ["etched_frost_film", "Etched / Frost Film"], ["specialty_custom_media", "Specialty / Custom Vehicle Media"],
];
const VEHICLE_LAMINATES = [["gloss", "Gloss"], ["matte", "Matte"], ["satin", "Satin"]];

/**
 * EC9 Phase 9E-1 — category-specific conditional fields for the 4 Core Flat
 * & Square-Foot calculators (Banners, Rigid Signs, Digital Print, Cut Vinyl).
 * EC9 Phase 9E-2 adds Apparel and Promotional Items.
 * EC9 Phase 9E-3 adds Vehicle Graphics & Wraps.
 * Progressive disclosure: dependent fields (grommet count, pole-pocket
 * sides, piece separation, design/install complexity) only render once
 * their parent toggle is on, so the form never shows more than what's
 * currently relevant.
 */
export function CategorySpecificFields({ category, values, onChange, designNeeded, installNeeded }) {
  const v = values || {};
  const set = (k) => (val) => onChange({ ...v, [k]: val });
  const Switchy = ({ testId, label, field }) => (
    <label className="flex items-center gap-2 text-sm cursor-pointer">
      <Switch checked={!!v[field]} onCheckedChange={set(field)} data-testid={testId} />{label}
    </label>
  );
  const Selecty = ({ testId, label, field, options, defaultValue }) => (
    <div className="grid gap-1.5">
      <Label className="text-xs">{label}</Label>
      <Select value={v[field] ?? defaultValue} onValueChange={set(field)}>
        <SelectTrigger data-testid={testId}><SelectValue /></SelectTrigger>
        <SelectContent>{options.map(([val, lbl]) => <SelectItem key={val} value={val}>{lbl}</SelectItem>)}</SelectContent>
      </Select>
    </div>
  );
  const Numbery = ({ testId, label, field, defaultValue = 0, min = 0 }) => (
    <div className="grid gap-1.5"><Label className="text-xs">{label}</Label>
      <Input type="number" min={min} value={v[field] ?? defaultValue} onChange={(e) => set(field)(Number(e.target.value))} data-testid={testId} />
    </div>
  );
  const Moneyy = ({ testId, label, field, defaultValue = 0 }) => (
    <div className="grid gap-1.5"><Label className="text-xs">{label}</Label>
      <Input type="number" min="0" step="0.01" value={v[field] ?? defaultValue} onChange={(e) => set(field)(Number(e.target.value))} data-testid={testId} />
    </div>
  );
  const PROVISIONAL_DECORATION_AREA_METHODS = new Set(["dtf_transfer", "sublimation"]);
  const FOUNDATION_ESTIMATE_METHODS = new Set(["dtf_transfer", "direct_screen_print", "embroidery", "dtg", "patch_emblem", "sublimation", "specialty_custom"]);

  const complexityFields = (
    <>
      {designNeeded && <Selecty testId="calc-design-complexity" label="Design complexity" field="design_complexity" defaultValue="simple"
        options={[["simple", "Simple"], ["medium", "Medium"], ["complex", "Complex"], ["extreme", "Extreme"]]} />}
      {installNeeded && <Selecty testId="calc-install-complexity" label="Install complexity" field="install_complexity" defaultValue="easy"
        options={[["easy", "Easy"], ["medium", "Medium"], ["difficult", "Difficult"], ["extreme", "Extreme"]]} />}
    </>
  );
  const rushAndCleanup = (
    <>
      <Switchy testId="calc-file-cleanup-switch" label="File cleanup needed" field="file_cleanup_needed" />
      <Switchy testId="calc-rush-switch" label="Rush" field="rush" />
    </>
  );

  if (category === "banners") {
    return (
      <div className="grid gap-3 rounded-lg border p-3" data-testid="calc-category-fields-banners">
        <div className="text-xs font-medium text-muted-foreground">Banner options</div>
        <div className="grid grid-cols-2 gap-3">
          <Selecty testId="calc-coating-type" label="Coating" field="coating_type" defaultValue="none"
            options={[["none", "None"], ["matte", "Matte laminate"], ["gloss", "Gloss laminate"]]} />
          <Selecty testId="calc-double-sided" label="Sided" field="double_sided" defaultValue="single"
            options={[["single", "Single-sided"], ["same_side", "Double — same side"], ["different_side", "Double — different sides"]]} />
        </div>
        <div className="grid grid-cols-2 gap-3">{complexityFields}</div>
        <div className="grid grid-cols-2 gap-3">
          <Switchy testId="calc-hems-switch" label="Hems" field="hems" />
          <Switchy testId="calc-reinforced-corners-switch" label="Reinforced corners" field="reinforced_corners" />
          <Switchy testId="calc-wind-slits-switch" label="Wind slits" field="wind_slits" />
          <Switchy testId="calc-specialty-sewing-switch" label="Specialty sewing" field="specialty_sewing" />
          <Switchy testId="calc-event-premium-switch" label="Event premium" field="event_premium" />
          <Switchy testId="calc-step-and-repeat-switch" label="Step-and-repeat" field="step_and_repeat" />
        </div>
        <div className="grid grid-cols-2 gap-3 items-end">
          <Selecty testId="calc-grommets-select" label="Grommets" field="grommets" defaultValue="none"
            options={[["none", "None"], ["standard", "Standard spacing"], ["custom", "Custom count"]]} />
          {v.grommets === "custom" && (
            <div className="grid gap-1.5"><Label className="text-xs">Grommet count</Label>
              <Input type="number" min="0" value={v.grommet_count ?? ""} onChange={(e) => set("grommet_count")(Number(e.target.value))} data-testid="calc-grommet-count-input" />
            </div>
          )}
        </div>
        <div className="grid grid-cols-2 gap-3 items-end">
          <Switchy testId="calc-pole-pockets-switch" label="Pole pockets" field="pole_pockets" />
          {v.pole_pockets && (
            <Selecty testId="calc-pole-pocket-sides" label="Pole pocket side(s)" field="pole_pocket_sides" defaultValue="top"
              options={[["top", "Top only"], ["top_bottom", "Top & bottom"]]} />
          )}
        </div>
        <div className="grid grid-cols-2 gap-3">{rushAndCleanup}</div>
      </div>
    );
  }

  if (category === "rigid_signs") {
    return (
      <div className="grid gap-3 rounded-lg border p-3" data-testid="calc-category-fields-rigid-signs">
        <div className="text-xs font-medium text-muted-foreground">Rigid sign options</div>
        <div className="grid grid-cols-2 gap-3">
          <Selecty testId="calc-graphic-method" label="Graphic method" field="graphic_method" defaultValue="direct_print"
            options={[["direct_print", "Direct print"], ["mounted_print", "Mounted print"], ["cut_vinyl_applied", "Cut vinyl applied"]]} />
          <Selecty testId="calc-shape-type" label="Shape" field="shape_type" defaultValue="standard"
            options={[["standard", "Standard"], ["custom_cut", "Custom cut"], ["complex_cut", "Complex cut"]]} />
          <Selecty testId="calc-finish-quality" label="Finish quality" field="finish_quality" defaultValue="standard"
            options={[["standard", "Standard"], ["premium", "Premium"], ["show_quality", "Show quality"]]} />
          <Selecty testId="calc-thickness" label="Thickness" field="thickness" defaultValue="standard"
            options={[["standard", "Standard"], ["heavy_duty", "Heavy-duty"], ["extra_heavy", "Extra heavy"]]} />
          <Selecty testId="calc-sidedness" label="Sidedness" field="sidedness" defaultValue="single"
            options={[["single", "Single-sided"], ["double", "Double-sided"]]} />
          <Selecty testId="calc-hardware-option" label="Hardware" field="hardware_option" defaultValue="none"
            options={[["none", "None"], ["h_stake", "Standard H-Stake"], ["heavy_duty_stake", "Heavy-Duty Stake"]]} />
        </div>
        <div className="grid grid-cols-2 gap-3">{complexityFields}</div>
        <Switchy testId="calc-drill-prep-switch" label="Drill / prep required" field="drill_prep_required" />
        <div className="grid grid-cols-2 gap-3"><Switchy testId="calc-rush-switch" label="Rush" field="rush" /></div>
      </div>
    );
  }

  if (category === "digital_print") {
    return (
      <div className="grid gap-3 rounded-lg border p-3" data-testid="calc-category-fields-digital-print">
        <div className="text-xs font-medium text-muted-foreground">Digital print options</div>
        <div className="grid grid-cols-2 gap-3">
          <Selecty testId="calc-quality-mode" label="Print quality" field="quality_mode" defaultValue="standard"
            options={[["draft", "Draft"], ["standard", "Standard"], ["high", "High"], ["photo", "Photo"]]} />
          <div className="grid gap-1.5"><Label className="text-xs">Ink coverage (%)</Label>
            <Input type="number" min="0" max="100" value={v.ink_coverage_percent ?? 75} onChange={(e) => set("ink_coverage_percent")(Number(e.target.value))} data-testid="calc-ink-coverage-input" />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Switchy testId="calc-laminate-switch" label="Laminate" field="laminate" />
          <Switchy testId="calc-mounted-switch" label="Mounted to substrate" field="mounted_to_substrate" />
          <Switchy testId="calc-contour-cut-switch" label="Contour cut" field="contour_cut" />
          {v.contour_cut && <Switchy testId="calc-piece-separation-switch" label="Piece separation" field="piece_separation" />}
        </div>
        <div className="grid grid-cols-2 gap-3">{complexityFields}</div>
        <div className="grid grid-cols-2 gap-3">{rushAndCleanup}</div>
      </div>
    );
  }

  if (category === "cut_vinyl") {
    return (
      <div className="grid gap-3 rounded-lg border p-3" data-testid="calc-category-fields-cut-vinyl">
        <div className="text-xs font-medium text-muted-foreground">Cut vinyl options</div>
        <div className="grid grid-cols-2 gap-3">
          <Selecty testId="calc-number-of-colors" label="Number of colors" field="number_of_colors" defaultValue="1"
            options={[["1", "1 color"], ["2", "2 colors"], ["3", "3 colors"], ["4_plus", "4+ colors"]]} />
          <Selecty testId="calc-weeding-complexity" label="Weeding complexity" field="weeding_complexity" defaultValue="simple"
            options={[["simple", "Simple"], ["medium", "Medium"], ["complex", "Complex"], ["extreme", "Extreme"]]} />
          <Selecty testId="calc-surface-type" label="Surface type (install)" field="surface_type" defaultValue="flat"
            options={[["flat", "Flat"], ["curved", "Curved"], ["awkward", "Awkward / high access"]]} />
        </div>
        <Switchy testId="calc-masking-switch" label="Masking required" field="masking" />
        <div className="grid grid-cols-2 gap-3">{complexityFields}</div>
        <div className="grid grid-cols-2 gap-3">{rushAndCleanup}</div>
      </div>
    );
  }

  if (category === "apparel") {
    const isHat = HAT_TYPES.has(v.garment_type || "short_sleeve_tee");
    const brandOptions = BRANDS_BY_GARMENT[v.garment_type] || BRANDS_BY_GARMENT.short_sleeve_tee;
    const placementOptions = isHat
      ? [["front_only", "Front only"], ["side_back", "Side-back"], ["front_side_back", "Front + Side/Back"]]
      : [["front_small", "Front small"], ["back_large", "Back large"], ["front_back", "Front + Back"]];
    return (
      <div className="grid gap-3 rounded-lg border p-3" data-testid="calc-category-fields-apparel">
        <div className="text-xs font-medium text-muted-foreground">Apparel options</div>
        <div className="grid grid-cols-2 gap-3">
          <Selecty testId="calc-apparel-garment-type" label="Garment / blank" field="garment_type" defaultValue="short_sleeve_tee" options={GARMENT_TYPES} />
          {!isHat && <Selecty testId="calc-apparel-brand" label="Brand" field="brand" defaultValue={brandOptions[0][0]} options={brandOptions} />}
          <Selecty testId="calc-apparel-placement" label="Decoration location" field="placement" defaultValue={isHat ? "front_side_back" : "front_back"} options={placementOptions} />
          <Selecty testId="calc-apparel-decoration-method" label="Decoration method" field="decoration_method" defaultValue="htv" options={DECORATION_METHODS} />
          <Numbery testId="calc-apparel-num-colors" label="Number of print colors" field="num_colors" defaultValue={1} min={1} />
          {v.decoration_method === "embroidery" && <Numbery testId="calc-apparel-stitch-count" label="Stitch count" field="stitch_count" defaultValue={0} />}
          {PROVISIONAL_DECORATION_AREA_METHODS.has(v.decoration_method) && (
            <Numbery testId="calc-apparel-decoration-area-sqin" label="Decoration area (sq in) — provisional, editable" field="decoration_area_sqin" defaultValue={16} />
          )}
        </div>
        {FOUNDATION_ESTIMATE_METHODS.has(v.decoration_method || "htv") && (
          <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800" data-testid="calc-apparel-provisional-warning">
            This decoration method uses a provisional Pricing Foundation cost-plus estimate — not an exact production-tested price table like HTV / Screen Print Transfer.
          </div>
        )}

        <div>
          <Label className="text-xs">Sizes (per-size quantity — leave blank to use the Quantity field above)</Label>
          <div className="grid grid-cols-5 sm:grid-cols-9 gap-2 mt-1.5">
            {SIZE_KEYS.map((sz) => (
              <div key={sz} className="grid gap-1">
                <Label className="text-[10px] text-muted-foreground text-center">{sz}</Label>
                <Input type="number" min="0" className="h-8 text-xs text-center" value={(v.sizes || {})[sz] ?? ""}
                  onChange={(e) => set("sizes")({ ...(v.sizes || {}), [sz]: Number(e.target.value) || 0 })}
                  data-testid={`calc-apparel-size-${sz.toLowerCase()}`} />
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Switchy testId="calc-apparel-customer-supplied-switch" label="Customer-supplied blank" field="customer_supplied" />
          <Switchy testId="calc-apparel-artwork-needed-switch" label="Artwork needed" field="artwork_needed" />
          {v.artwork_needed && <Selecty testId="calc-apparel-design-complexity" label="Design complexity" field="design_complexity" defaultValue="simple"
            options={[["simple", "Simple"], ["medium", "Medium"], ["complex", "Complex"], ["extreme", "Extreme"]]} />}
        </div>

        <div className="grid grid-cols-2 gap-3 items-end">
          <Switchy testId="calc-apparel-custom-name-number-switch" label="Custom name / number" field="custom_name_number" />
          {v.custom_name_number && <Numbery testId="calc-apparel-custom-name-number-count" label="Name/number count" field="custom_name_number_count" defaultValue={0} />}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Switchy testId="calc-apparel-specialty-finish-switch" label={isHat ? "Specialty finish (+$1.50 ea)" : "Specialty vinyl/finish (+$2 ea)"} field="specialty_finish" />
          <Switchy testId="calc-apparel-bag-and-fold-switch" label="Bag & fold" field="bag_and_fold" />
          {isHat && <Switchy testId="calc-apparel-two-tone-hat-switch" label="Two-tone / specialty hat finish" field="two_tone_hat_finish" />}
          {isHat && <Switchy testId="calc-apparel-leather-patch-switch" label="Leather / faux patch" field="leather_patch" />}
        </div>

        <div className="grid grid-cols-2 gap-3 items-end">
          <Switchy testId="calc-apparel-rush-switch" label="Rush" field="rush" />
          {v.rush && <Numbery testId="calc-apparel-rush-percent" label="Rush % override" field="rush_percent" defaultValue={17.5} />}
        </div>
      </div>
    );
  }

  if (category === "vehicle_graphics") {
    return (
      <div className="grid gap-3 rounded-lg border p-3" data-testid="calc-category-fields-vehicle-graphics">
        <div className="text-xs font-medium text-muted-foreground">Vehicle graphics / wrap options</div>
        <div className="grid grid-cols-2 gap-3">
          <Selecty testId="calc-vehicle-type" label="Vehicle type" field="vehicle_type" defaultValue="sedan" options={VEHICLE_TYPES} />
          <Selecty testId="calc-vehicle-coverage-type" label="Coverage type" field="coverage_type" defaultValue="partial" options={VEHICLE_COVERAGE_TYPES} />
          {v.coverage_type === "custom" && <Numbery testId="calc-vehicle-coverage-percent" label="Custom coverage %" field="coverage_percent" defaultValue={40} />}
          <Numbery testId="calc-vehicle-estimated-sqft-override" label="Override estimated sq ft (optional)" field="estimated_sqft_override" defaultValue="" />
        </div>

        <div className="grid grid-cols-2 gap-3 items-end">
          <Selecty testId="calc-vehicle-wrap-material" label="Wrap material" field="wrap_material" defaultValue="standard_calendared_vinyl" options={VEHICLE_MATERIALS} />
          <Switchy testId="calc-vehicle-laminate-required-switch" label="Laminate required" field="laminate_required" />
          {v.laminate_required && <Selecty testId="calc-vehicle-laminate-type" label="Laminate type" field="laminate_type" defaultValue="gloss" options={VEHICLE_LAMINATES} />}
        </div>

        <div className="grid grid-cols-3 gap-3 items-end">
          <Selecty testId="calc-vehicle-window-perf-type" label="Window perf" field="window_perf_type" defaultValue="none"
            options={[["none", "None"], ["rear_only", "Rear window only"], ["side_windows", "Side windows"]]} />
          {v.window_perf_type && v.window_perf_type !== "none" && (
            <Numbery testId="calc-vehicle-window-perf-sqft" label="Window perf sq ft (measured)" field="window_perf_sqft" defaultValue={0} />
          )}
        </div>

        <div className="grid grid-cols-2 gap-3 items-end">
          <Switchy testId="calc-vehicle-design-needed-switch" label="Design needed" field="design_needed" />
          {v.design_needed && <Selecty testId="calc-vehicle-design-complexity" label="Design complexity" field="design_complexity" defaultValue="simple"
            options={[["simple", "Simple"], ["medium", "Medium"], ["complex", "Complex"], ["extreme", "Extreme"]]} />}
          <Switchy testId="calc-vehicle-file-cleanup-switch" label="File cleanup needed" field="file_cleanup_needed" />
        </div>

        <div className="grid grid-cols-2 gap-3 items-end">
          <Selecty testId="calc-vehicle-surface-prep" label="Surface prep" field="surface_prep" defaultValue="none"
            options={[["none", "None"], ["basic", "Basic"], ["moderate", "Moderate"], ["heavy", "Heavy"]]} />
          <Selecty testId="calc-vehicle-removal-required" label="Removal required" field="removal_required" defaultValue="none"
            options={[["none", "None"], ["small", "Small"], ["partial", "Partial"], ["full", "Full"]]} />
        </div>

        <div className="grid grid-cols-2 gap-3 items-end">
          <Switchy testId="calc-vehicle-install-needed-switch" label="Install needed" field="install_needed" />
          {v.install_needed !== false && (
            <>
              <Selecty testId="calc-vehicle-install-difficulty" label="Install difficulty" field="install_difficulty" defaultValue="easy"
                options={[["easy", "Easy"], ["medium", "Medium"], ["difficult", "Difficult"], ["extreme", "Extreme"]]} />
              <Selecty testId="calc-vehicle-seam-complexity" label="Seam / panel complexity" field="seam_complexity" defaultValue="basic"
                options={[["basic", "Basic"], ["moderate", "Moderate"], ["advanced", "Advanced"]]} />
              <Switchy testId="calc-vehicle-helper-required-switch" label="2nd installer / helper" field="helper_required" />
            </>
          )}
        </div>

        <div className="grid grid-cols-3 gap-3 items-end">
          <Switchy testId="calc-vehicle-travel-required-switch" label="Travel required" field="travel_required" />
          {v.travel_required && <Numbery testId="calc-vehicle-travel-miles" label="Travel miles" field="travel_miles" defaultValue={0} />}
          <Switchy testId="calc-vehicle-rush-switch" label="Rush" field="rush" />
        </div>
      </div>
    );
  }

  if (category === "promotional") {
    return (
      <div className="grid gap-3 rounded-lg border p-3" data-testid="calc-category-fields-promotional">
        <div className="text-xs font-medium text-muted-foreground">Promotional item options</div>
        <div className="grid grid-cols-2 gap-3">
          <div className="grid gap-1.5"><Label className="text-xs">Order item name</Label>
            <Input value={v.order_item_name ?? ""} onChange={(e) => set("order_item_name")(e.target.value)} data-testid="calc-promo-order-item-name-input" /></div>
          <div className="grid gap-1.5"><Label className="text-xs">Promotional item type</Label>
            <Input placeholder="e.g. pens, mugs, koozies" value={v.promotional_item_type ?? ""} onChange={(e) => set("promotional_item_type")(e.target.value)} data-testid="calc-promo-item-type-input" /></div>
        </div>
        <div className="grid gap-1.5"><Label className="text-xs">Description</Label>
          <Input value={v.description ?? ""} onChange={(e) => set("description")(e.target.value)} data-testid="calc-promo-description-input" /></div>

        <div className="grid grid-cols-2 gap-3">
          <Selecty testId="calc-promo-pricing-method" label="Pricing method" field="pricing_method" defaultValue="manual"
            options={[["tier_pricing", "Tier pricing (saved item)"], ["per_piece", "Per-piece"], ["flat_fee", "Flat fee"], ["manual", "Manual"]]} />
          {v.pricing_method === "flat_fee" && <Moneyy testId="calc-promo-flat-fee-price" label="Flat fee sell price" field="flat_fee_price" defaultValue={0} />}
        </div>

        <div className="grid grid-cols-2 gap-3 items-end">
          <div className="grid gap-1.5"><Label className="text-xs">Vendor / supplier</Label>
            <Input value={v.vendor_supplier ?? ""} onChange={(e) => set("vendor_supplier")(e.target.value)} data-testid="calc-promo-vendor-input" /></div>
          <Switchy testId="calc-promo-known-supplier-cost-switch" label="Known supplier cost?" field="known_supplier_cost" />
          {v.known_supplier_cost !== false && <Moneyy testId="calc-promo-unit-cost-input" label="Unit cost" field="unit_cost" defaultValue={0} />}
        </div>

        <div className="grid grid-cols-2 gap-3 items-end">
          <Switchy testId="calc-promo-setup-required-switch" label="Setup required?" field="setup_required" />
          {v.setup_required && <Moneyy testId="calc-promo-setup-fee-input" label="Setup fee" field="setup_fee" defaultValue={0} />}
        </div>

        <div className="grid grid-cols-2 gap-3 items-end">
          <div className="grid gap-1.5"><Label className="text-xs">Decoration method</Label>
            <Input value={v.decoration_method ?? ""} onChange={(e) => set("decoration_method")(e.target.value)} data-testid="calc-promo-decoration-method-input" /></div>
          <div className="grid gap-1.5"><Label className="text-xs">Decoration location</Label>
            <Input value={v.decoration_location ?? ""} onChange={(e) => set("decoration_location")(e.target.value)} data-testid="calc-promo-decoration-location-input" /></div>
        </div>
        <div className="grid grid-cols-3 gap-3 items-end">
          <Switchy testId="calc-promo-decoration-fee-required-switch" label="Decoration fee required?" field="decoration_fee_required" />
          {v.decoration_fee_required && (
            <>
              <Selecty testId="calc-promo-decoration-fee-type" label="Fee type" field="decoration_fee_type" defaultValue="per_piece"
                options={[["per_piece", "Per piece"], ["flat_fee", "Flat fee"]]} />
              <Moneyy testId="calc-promo-decoration-fee-amount" label="Decoration fee" field="decoration_fee_amount" defaultValue={0} />
            </>
          )}
        </div>

        <div className="grid grid-cols-3 gap-3 items-end">
          <Switchy testId="calc-promo-personalization-required-switch" label="Personalization required?" field="personalization_required" />
          {v.personalization_required && (
            <>
              <Numbery testId="calc-promo-personalization-count" label="Personalization count" field="personalization_count" defaultValue={0} />
              <Moneyy testId="calc-promo-personalization-fee" label="Personalization fee (ea)" field="personalization_fee" defaultValue={0} />
            </>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3 items-end">
          <Switchy testId="calc-promo-shipping-required-switch" label="Shipping / pass-through required?" field="shipping_required" />
          {v.shipping_required && <Moneyy testId="calc-promo-shipping-cost" label="Shipping / pass-through cost" field="shipping_cost" defaultValue={0} />}
        </div>

        <Switchy testId="calc-promo-rush-switch" label="Rush" field="rush" />
      </div>
    );
  }

  return null;
}
