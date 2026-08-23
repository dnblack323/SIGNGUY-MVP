import { useState } from "react";
import { Upload, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { extractError } from "@/lib/api";
import { uploadWebstoreSetupFile } from "@/lib/webstores";
import portalApi, { portalExtractError } from "@/portal/portalApi";
import { toast } from "sonner";
import { getPath, setPath } from "./WebstoreBrandingUtils";

const IMAGE_HINTS = {
  "primary-logo": "Recommended: 600 x 300 transparent PNG, JPG, WebP, or safe SVG logo.",
  "alternate-logo": "Recommended: 600 x 300 alternate PNG, JPG, WebP, or safe SVG logo for dark backgrounds.",
  favicon: "Recommended: 512 x 512 square PNG, JPG, WebP, or safe SVG icon.",
  "social-image": "Recommended: 1200 x 630 JPG, PNG, or WebP social-sharing image.",
  "hero-image": "Recommended: 1600 x 600 JPG, PNG, or WebP wide hero image.",
  "supporting-image": "Recommended: 900 x 600 JPG, PNG, or WebP supporting image.",
};

const LOGO_UPLOAD_SLOTS = new Set(["primary-logo", "alternate-logo", "favicon"]);

function safeDestination(destination) {
  if (destination === "store_information") return "#store-information";
  if (destination === "contact") return "#store-footer";
  if (destination === "none") return undefined;
  return "#catalog";
}

function headingFontFamily(font) {
  if (font === "serif") return "Georgia, serif";
  if (font === "display") return "'Trebuchet MS', 'Arial Black', sans-serif";
  if (font === "condensed") return "'Arial Narrow', Arial, sans-serif";
  return "Inter, system-ui, sans-serif";
}

function overlayColor(hex) {
  const value = /^#[0-9a-fA-F]{6}$/.test(hex || "") ? hex : "#000000";
  const r = parseInt(value.slice(1, 3), 16);
  const g = parseInt(value.slice(3, 5), 16);
  const b = parseInt(value.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, 0.42)`;
}

function ImageControl({ label, value = {}, onChange, slot, portal, webstoreId, disabled }) {
  const [localError, setLocalError] = useState("");
  const logoSlot = LOGO_UPLOAD_SLOTS.has(slot);
  const hint = IMAGE_HINTS[slot] || "Recommended: web-ready JPG, PNG, or WebP image with descriptive alt text.";
  async function upload(file) {
    if (!file) return;
    const ext = file.name.split(".").pop().toLowerCase();
    if (["ai", "eps"].includes(ext)) {
      setLocalError("Upload a web-ready JPG, PNG, WebP, or supported logo SVG instead of AI or EPS artwork.");
      return;
    }
    if (!["jpg", "jpeg", "png", "webp", "svg"].includes(ext) || (ext === "svg" && !logoSlot)) {
      setLocalError("Upload a supported web image: JPG, PNG, WebP, or SVG for logos only.");
      return;
    }
    const formData = new FormData();
    formData.append("category", `branding-${slot}`);
    formData.append("file", file);
    try {
      const response = portal
        ? await portalApi.post(`/portal/webstores/${webstoreId}/setup-files`, formData, { headers: { "Content-Type": "multipart/form-data" } })
        : await uploadWebstoreSetupFile(webstoreId, formData);
      const fileDoc = response?.data?.file || response?.file;
      onChange({
        ...value,
        file_id: fileDoc.id,
        file_name: fileDoc.file_name,
        content_type: fileDoc.detected_content_type || file.type,
        url: URL.createObjectURL(file),
      });
      setLocalError("");
      toast.success("Branding image uploaded");
    } catch (error) {
      setLocalError(portal ? portalExtractError(error) : extractError(error));
    }
  }
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-2">
        <Input
          value={value.url || value.file_name || ""}
          onChange={(e) => onChange(e.target.value ? { ...value, url: e.target.value } : {})}
          placeholder="Image URL or uploaded file"
          disabled={disabled}
          data-testid={`branding-image-${slot}`}
        />
        <label className="inline-flex items-center justify-center rounded-md border px-3 py-2 text-sm cursor-pointer hover:bg-slate-50">
          <Upload className="size-4 mr-2" />Upload
          <input className="sr-only" type="file" accept={logoSlot ? ".jpg,.jpeg,.png,.webp,.svg" : ".jpg,.jpeg,.png,.webp"} disabled={disabled} onChange={(e) => upload(e.target.files?.[0])} data-testid={`branding-upload-${slot}`} />
        </label>
      </div>
      {(value.url || value.file_id || value.file_name) && (
        <div className="flex items-center gap-3 rounded border bg-slate-50 p-2">
          {value.url && <img alt={value.alt_text || label} src={value.url} className="h-12 w-20 rounded object-cover" />}
          <Button type="button" size="sm" variant="outline" disabled={disabled} onClick={() => { onChange({}); setLocalError(""); }} data-testid={`branding-remove-${slot}`}>
            <X className="size-4 mr-2" />Remove
          </Button>
        </div>
      )}
      <Input
        value={value.alt_text || ""}
        onChange={(e) => onChange({ ...value, alt_text: e.target.value })}
        placeholder="Alt text"
        disabled={disabled}
        data-testid={`branding-alt-${slot}`}
      />
      <div className="text-xs text-muted-foreground">{hint}</div>
      {localError && <div className="text-xs text-rose-700">{localError}</div>}
    </div>
  );
}
function Field({ label, path, draft, onDraft, type = "text", disabled = false, rows = 3 }) {
  const value = getPath(draft, path) ?? "";
  if (type === "textarea") {
    return (
      <div className="grid gap-1.5">
        <Label>{label}</Label>
        <Textarea rows={rows} value={value} disabled={disabled} onChange={(e) => onDraft(setPath(draft, path, e.target.value))} data-testid={`branding-field-${path}`} />
      </div>
    );
  }
  if (type === "checkbox") {
    return (
      <label className="flex items-center gap-2 text-sm">
        <Checkbox checked={!!value} disabled={disabled} onCheckedChange={(checked) => onDraft(setPath(draft, path, !!checked))} data-testid={`branding-field-${path}`} />
        {label}
      </label>
    );
  }
  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      <Input type={type} value={value} disabled={disabled} onChange={(e) => onDraft(setPath(draft, path, e.target.value))} data-testid={`branding-field-${path}`} />
    </div>
  );
}

function SelectField({ label, path, draft, onDraft, options, disabled = false }) {
  const value = getPath(draft, path) || options[0]?.value;
  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      <Select value={value} onValueChange={(next) => onDraft(setPath(draft, path, next))} disabled={disabled}>
        <SelectTrigger data-testid={`branding-field-${path}`}><SelectValue /></SelectTrigger>
        <SelectContent>{options.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent>
      </Select>
    </div>
  );
}

function StoreTypeFields({ storeType, draft, onDraft }) {
  if (storeType === "b2b") {
    return (
      <>
        <Field label="Business welcome wording" path="store_type_content.business_welcome" draft={draft} onDraft={onDraft} />
        <Field label="Account or ordering instructions" path="store_type_content.ordering_instructions" draft={draft} onDraft={onDraft} type="textarea" />
        <Field label="Access notice" path="store_type_content.access_notice" draft={draft} onDraft={onDraft} />
        <Field label="Fulfillment or pickup summary" path="store_type_content.fulfillment_summary" draft={draft} onDraft={onDraft} />
      </>
    );
  }
  if (storeType === "fundraiser") {
    return (
      <>
        <Field label="Organization or team display name" path="store_type_content.organization_name" draft={draft} onDraft={onDraft} />
        <Field label="Campaign story heading" path="store_type_content.campaign_heading" draft={draft} onDraft={onDraft} />
        <Field label="Campaign message" path="store_type_content.campaign_message" draft={draft} onDraft={onDraft} type="textarea" />
        <Field label="Proceeds explanation" path="store_type_content.proceeds_explanation" draft={draft} onDraft={onDraft} />
        <Field label="Show goal/progress area" path="store_type_content.show_goal_progress" draft={draft} onDraft={onDraft} type="checkbox" />
        <Field label="Show campaign end date" path="store_type_content.show_campaign_end_date" draft={draft} onDraft={onDraft} type="checkbox" />
      </>
    );
  }
  if (storeType === "event") {
    return (
      <>
        <Field label="Event display name" path="store_type_content.event_display_name" draft={draft} onDraft={onDraft} />
        <Field label="Event information heading" path="store_type_content.event_heading" draft={draft} onDraft={onDraft} />
        <Field label="Event message" path="store_type_content.event_message" draft={draft} onDraft={onDraft} type="textarea" />
        <Field label="Show event date/time" path="store_type_content.show_event_datetime" draft={draft} onDraft={onDraft} type="checkbox" />
        <Field label="Show location" path="store_type_content.show_location" draft={draft} onDraft={onDraft} type="checkbox" />
        <Field label="Show ordering deadline" path="store_type_content.show_ordering_deadline" draft={draft} onDraft={onDraft} type="checkbox" />
        <Field label="Pickup instructions" path="store_type_content.pickup_instructions" draft={draft} onDraft={onDraft} />
      </>
    );
  }
  if (storeType === "promotional") {
    return (
      <>
        <Field label="Campaign heading" path="store_type_content.campaign_heading" draft={draft} onDraft={onDraft} />
        <Field label="Campaign message" path="store_type_content.campaign_message" draft={draft} onDraft={onDraft} type="textarea" />
        <Field label="Offer or promotion wording" path="store_type_content.offer_wording" draft={draft} onDraft={onDraft} />
        <Field label="Show deadline" path="store_type_content.show_deadline" draft={draft} onDraft={onDraft} type="checkbox" />
        <Field label="Promotion badge" path="store_type_content.promotion_badge" draft={draft} onDraft={onDraft} />
      </>
    );
  }
  if (storeType === "employee") {
    return (
      <>
        <Field label="Company welcome wording" path="store_type_content.company_welcome" draft={draft} onDraft={onDraft} />
        <Field label="Employee ordering instructions" path="store_type_content.employee_ordering_instructions" draft={draft} onDraft={onDraft} type="textarea" />
        <Field label="Access notice" path="store_type_content.access_notice" draft={draft} onDraft={onDraft} />
        <Field label="Fulfillment or distribution message" path="store_type_content.fulfillment_message" draft={draft} onDraft={onDraft} />
      </>
    );
  }
  return (
    <>
      <Field label="General welcome message" path="store_type_content.general_welcome" draft={draft} onDraft={onDraft} />
      <Field label="About-the-store content" path="store_type_content.about_store" draft={draft} onDraft={onDraft} type="textarea" />
      <Field label="Shopping instructions" path="store_type_content.shopping_instructions" draft={draft} onDraft={onDraft} />
    </>
  );
}

export function CategoryControls({ category, draft, onDraft, permissions, portal, webstoreId, storeType }) {
  const canControlWhole = !!permissions?.can_control_whole_sections;
  if (category === "brand_basics") {
    return (
      <>
        <Field label="Displayed store name" path="brand_basics.display_name" draft={draft} onDraft={onDraft} />
        <Field label="Short tagline" path="brand_basics.tagline" draft={draft} onDraft={onDraft} />
        <ImageControl label="Primary logo" value={draft.brand_basics?.primary_logo} onChange={(v) => onDraft(setPath(draft, "brand_basics.primary_logo", v))} slot="primary-logo" portal={portal} webstoreId={webstoreId} />
        <ImageControl label="Alternate logo" value={draft.brand_basics?.alternate_logo} onChange={(v) => onDraft(setPath(draft, "brand_basics.alternate_logo", v))} slot="alternate-logo" portal={portal} webstoreId={webstoreId} />
        <ImageControl label="Browser/store icon" value={draft.brand_basics?.favicon} onChange={(v) => onDraft(setPath(draft, "brand_basics.favicon", v))} slot="favicon" portal={portal} webstoreId={webstoreId} />
        <ImageControl label="Social-sharing image" value={draft.brand_basics?.social_image} onChange={(v) => onDraft(setPath(draft, "brand_basics.social_image", v))} slot="social-image" portal={portal} webstoreId={webstoreId} />
      </>
    );
  }
  if (category === "colors_fonts") {
    return (
      <>
        {["primary_color", "secondary_color", "accent_color", "page_background_color", "main_text_color", "button_background_color", "button_text_color"].map((key) => (
          <Field key={key} type="color" label={key.replace(/_/g, " ")} path={`colors_fonts.${key}`} draft={draft} onDraft={onDraft} />
        ))}
        <SelectField label="Heading font" path="colors_fonts.heading_font" draft={draft} onDraft={onDraft} options={[
          { value: "inter", label: "Inter" }, { value: "system", label: "System" }, { value: "serif", label: "Serif" }, { value: "display", label: "Display" }, { value: "condensed", label: "Condensed" },
        ]} />
        <SelectField label="Body font" path="colors_fonts.body_font" draft={draft} onDraft={onDraft} options={[
          { value: "inter", label: "Inter" }, { value: "system", label: "System" }, { value: "serif", label: "Serif" }, { value: "display", label: "Display" }, { value: "condensed", label: "Condensed" },
        ]} />
        <SelectField label="Button corner style" path="colors_fonts.button_corner_style" draft={draft} onDraft={onDraft} options={[
          { value: "square", label: "Square" }, { value: "slightly_rounded", label: "Slightly rounded" }, { value: "rounded", label: "Rounded" },
        ]} />
      </>
    );
  }
  if (category === "header") {
    return (
      <>
        <Field label="Show entire header" path="header.show_header" draft={draft} onDraft={onDraft} type="checkbox" disabled={!canControlWhole} />
        <SelectField label="Header display" path="header.display_mode" draft={draft} onDraft={onDraft} options={[
          { value: "name", label: "Store name" }, { value: "logo", label: "Logo" }, { value: "both", label: "Logo and name" },
        ]} />
        <SelectField label="Logo size" path="header.logo_size" draft={draft} onDraft={onDraft} options={[
          { value: "small", label: "Small" }, { value: "medium", label: "Medium" }, { value: "large", label: "Large" },
        ]} />
        <Field type="color" label="Header background color" path="header.background_color" draft={draft} onDraft={onDraft} />
        <Field label="Announcement bar on" path="header.announcement_enabled" draft={draft} onDraft={onDraft} type="checkbox" />
        <Field label="Announcement text" path="header.announcement_text" draft={draft} onDraft={onDraft} />
        <Field type="color" label="Announcement background" path="header.announcement_background_color" draft={draft} onDraft={onDraft} />
        <Field type="color" label="Announcement text color" path="header.announcement_text_color" draft={draft} onDraft={onDraft} />
        <SelectField label="Announcement link destination" path="header.announcement_link_destination" draft={draft} onDraft={onDraft} options={[
          { value: "none", label: "None" }, { value: "catalog", label: "Product area" }, { value: "store_information", label: "Store information" }, { value: "contact", label: "Contact" },
        ]} />
      </>
    );
  }
  if (category === "hero") {
    return (
      <>
        <Field label="Show entire hero" path="hero.show_hero" draft={draft} onDraft={onDraft} type="checkbox" disabled={!canControlWhole} />
        <ImageControl label="Hero image" value={draft.hero?.image} onChange={(v) => onDraft(setPath(draft, "hero.image", v))} slot="hero-image" portal={portal} webstoreId={webstoreId} />
        <SelectField label="Image focal position" path="hero.image_focal_position" draft={draft} onDraft={onDraft} options={[
          { value: "left", label: "Left" }, { value: "center", label: "Center" }, { value: "right", label: "Right" },
        ]} />
        <Field type="color" label="Color overlay" path="hero.overlay_color" draft={draft} onDraft={onDraft} />
        <Field label="Main headline" path="hero.headline" draft={draft} onDraft={onDraft} />
        <Field label="Supporting text" path="hero.supporting_text" draft={draft} onDraft={onDraft} type="textarea" />
        <Field label="Primary button on" path="hero.primary_button_enabled" draft={draft} onDraft={onDraft} type="checkbox" />
        <Field label="Primary button label" path="hero.primary_button_label" draft={draft} onDraft={onDraft} />
        <SelectField label="Primary button destination" path="hero.primary_button_destination" draft={draft} onDraft={onDraft} options={[
          { value: "catalog", label: "Product area" }, { value: "store_information", label: "Store information" }, { value: "contact", label: "Contact" }, { value: "none", label: "None" },
        ]} />
      </>
    );
  }
  if (category === "store_information") {
    return (
      <>
        <Field label="Show Store Information section" path="store_information.show_section" draft={draft} onDraft={onDraft} type="checkbox" />
        <Field label="Welcome heading" path="store_information.welcome_heading" draft={draft} onDraft={onDraft} />
        <Field label="Welcome or About text" path="store_information.welcome_text" draft={draft} onDraft={onDraft} type="textarea" />
        <ImageControl label="Supporting image" value={draft.store_information?.supporting_image} onChange={(v) => onDraft(setPath(draft, "store_information.supporting_image", v))} slot="supporting-image" portal={portal} webstoreId={webstoreId} />
        <Field label="Store instructions" path="store_information.store_instructions" draft={draft} onDraft={onDraft} type="textarea" />
        <SelectField label="Contact display options" path="store_information.contact_display" draft={draft} onDraft={onDraft} options={[
          { value: "store", label: "Store contact" }, { value: "shop", label: "Shop contact" }, { value: "hidden", label: "Hidden" },
        ]} />
      </>
    );
  }
  if (category === "store_type_content") {
    return <StoreTypeFields storeType={storeType} draft={draft} onDraft={onDraft} />;
  }
  if (category === "catalog_introduction") {
    return (
      <>
        <Field label="Show catalog area" path="catalog_introduction.show_catalog_area" draft={draft} onDraft={onDraft} type="checkbox" disabled={!canControlWhole} />
        <Field label="Catalog section heading" path="catalog_introduction.heading" draft={draft} onDraft={onDraft} />
        <Field label="Short catalog introduction" path="catalog_introduction.introduction" draft={draft} onDraft={onDraft} type="textarea" />
        <Field type="color" label="Catalog background color" path="catalog_introduction.background_color" draft={draft} onDraft={onDraft} />
      </>
    );
  }
  return (
    <>
      <Field label="Show footer" path="footer.show_footer" draft={draft} onDraft={onDraft} type="checkbox" />
      <Field type="color" label="Footer background color" path="footer.background_color" draft={draft} onDraft={onDraft} />
      <Field type="color" label="Footer text color" path="footer.text_color" draft={draft} onDraft={onDraft} />
      <SelectField label="Show logo or store name" path="footer.display_mode" draft={draft} onDraft={onDraft} options={[
        { value: "store_name", label: "Store name" }, { value: "logo", label: "Logo" }, { value: "both", label: "Logo and name" },
      ]} />
      <Field label="Short footer message" path="footer.message" draft={draft} onDraft={onDraft} />
      <Field label="Show contact information" path="footer.show_contact" draft={draft} onDraft={onDraft} type="checkbox" />
      <Field label="Show social links" path="footer.show_social_links" draft={draft} onDraft={onDraft} type="checkbox" />
      <Field label="Show policy links" path="footer.show_policy_links" draft={draft} onDraft={onDraft} type="checkbox" />
      <Field label="Show Powered by branding" path="footer.show_powered_by" draft={draft} onDraft={onDraft} type="checkbox" />
    </>
  );
}
