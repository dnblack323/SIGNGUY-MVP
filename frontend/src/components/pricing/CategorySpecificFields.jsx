import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

/**
 * EC9 Phase 9E-1 — category-specific conditional fields for the 4 Core Flat
 * & Square-Foot calculators (Banners, Rigid Signs, Digital Print, Cut Vinyl).
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

  return null;
}
