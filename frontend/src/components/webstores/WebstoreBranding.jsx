import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Eye, MessageSquare, Send, Upload, Save, Rocket, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { extractError } from "@/lib/api";
import {
  getWebstoreBranding,
  listWebstoreSetupFiles,
  publishWebstoreBranding,
  requestWebstoreBrandingReview,
  saveWebstoreBrandingDraft,
  uploadWebstoreSetupFile,
} from "@/lib/webstores";
import portalApi, { portalExtractError } from "@/portal/portalApi";
import { toast } from "sonner";

const CATEGORY_CARDS = [
  ["brand_basics", "Brand Basics"],
  ["colors_fonts", "Colors & Fonts"],
  ["header", "Header"],
  ["hero", "Hero Section"],
  ["store_information", "Store Information"],
  ["store_type_content", "Store-Type Content"],
  ["catalog_introduction", "Catalog Introduction"],
  ["footer", "Footer"],
];

const STATUS_LABELS = {
  draft: "Draft",
  waiting_owner_approval: "Waiting for Owner Approval",
  changes_requested: "Changes Requested",
  owner_approved: "Owner Approved",
  published: "Published",
};

const TYPE_LABELS = {
  b2b: "B2B",
  fundraiser: "Fundraiser",
  event: "Event",
  promotional: "Promotional",
  employee: "Employee Store",
  general: "General Store",
};

function getPath(data, path) {
  return path.split(".").reduce((current, part) => current?.[part], data);
}

function setPath(data, path, value) {
  const parts = path.split(".");
  const copy = JSON.parse(JSON.stringify(data || {}));
  let cursor = copy;
  parts.slice(0, -1).forEach((part) => {
    cursor[part] = cursor[part] || {};
    cursor = cursor[part];
  });
  cursor[parts[parts.length - 1]] = value;
  return copy;
}

function statusLabel(status) {
  return STATUS_LABELS[status] || "Draft";
}

function buttonRadius(style) {
  if (style === "square") return "0px";
  if (style === "rounded") return "999px";
  return "8px";
}

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

function CategoryControls({ category, draft, onDraft, permissions, portal, webstoreId, storeType }) {
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

function TypeContentPreview({ storeType, content = {} }) {
  const label = TYPE_LABELS[storeType] || "General Store";
  const lines = {
    b2b: [content.business_welcome, content.ordering_instructions, content.access_notice, content.fulfillment_summary],
    fundraiser: [
      content.organization_name,
      content.campaign_heading,
      content.campaign_message,
      content.proceeds_explanation,
      content.show_goal_progress ? "Goal and progress information will display when campaign totals are available." : "",
      content.show_campaign_end_date ? "Campaign end date will display when configured in Store Setup." : "",
    ],
    event: [
      content.event_display_name,
      content.event_heading,
      content.event_message,
      content.show_event_datetime ? "Event date and time will display from Store Setup." : "",
      content.show_location ? "Event location will display from Store Setup." : "",
      content.show_ordering_deadline ? "Ordering deadline will display from Store Setup." : "",
      content.pickup_instructions,
    ],
    promotional: [
      content.campaign_heading,
      content.campaign_message,
      content.offer_wording,
      content.show_deadline ? "Promotion deadline will display when configured." : "",
      content.promotion_badge,
    ],
    employee: [content.company_welcome, content.employee_ordering_instructions, content.access_notice, content.fulfillment_message],
    general: [content.general_welcome, content.about_store, content.shopping_instructions],
  }[storeType] || [];
  return (
    <section className="px-5 py-4 border-t" data-testid={`branding-preview-type-${storeType}`}>
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      {lines.filter(Boolean).map((line, index) => <p key={`${line}-${index}`} className="mt-1 text-sm">{line}</p>)}
    </section>
  );
}

export function WebstoreBrandingPreview({ branding = {}, webstore = {}, products = [], compact = false, draft = false }) {
  const basics = branding.brand_basics || {};
  const colors = branding.colors_fonts || {};
  const header = branding.header || {};
  const hero = branding.hero || {};
  const info = branding.store_information || {};
  const catalog = branding.catalog_introduction || {};
  const footer = branding.footer || {};
  const style = {
    backgroundColor: colors.page_background_color || "#f8fafc",
    color: colors.main_text_color || "#111827",
    fontFamily: colors.body_font === "serif" ? "Georgia, serif" : "Inter, system-ui, sans-serif",
  };
  const headingStyle = {
    color: colors.primary_color || "#0f172a",
    fontFamily: headingFontFamily(colors.heading_font),
  };
  const buttonStyle = {
    backgroundColor: colors.button_background_color || "#2563eb",
    color: colors.button_text_color || "#ffffff",
    borderRadius: buttonRadius(colors.button_corner_style),
    borderColor: colors.accent_color || colors.button_background_color || "#2563eb",
  };
  const heroImage = hero.image || {};
  const heroFocal = hero.image_focal_position || heroImage.focal_position || "center";
  const heroStyle = {
    backgroundColor: colors.secondary_color || "#1e293b",
    color: "#ffffff",
    ...(heroImage.url
      ? {
          backgroundImage: `linear-gradient(${overlayColor(hero.overlay_color)}, ${overlayColor(hero.overlay_color)}), url("${heroImage.url}")`,
          backgroundSize: "cover",
          backgroundPosition: `${heroFocal} center`,
        }
      : {}),
  };
  const buttonHref = safeDestination(hero.primary_button_destination);
  return (
    <div className={`overflow-hidden rounded border bg-white ${compact ? "max-w-sm" : ""}`} style={style} data-testid={compact ? "branding-mobile-preview" : "branding-desktop-preview"}>
      {draft && <div className="bg-amber-100 px-4 py-2 text-xs font-medium text-amber-900">Draft Preview</div>}
      {header.show_header !== false && (
        <header style={{ backgroundColor: header.background_color || "#ffffff" }} className="border-b" data-testid="branding-preview-header">
          {header.announcement_enabled && (
            <div className="px-4 py-2 text-center text-xs" style={{ backgroundColor: header.announcement_background_color, color: header.announcement_text_color }} data-testid="branding-preview-announcement">
              {safeDestination(header.announcement_link_destination) ? (
                <a href={safeDestination(header.announcement_link_destination)}>{header.announcement_text}</a>
              ) : header.announcement_text}
            </div>
          )}
          <div className="flex items-center gap-3 px-5 py-4">
            {["logo", "both"].includes(header.display_mode) && basics.primary_logo?.url && <img alt={basics.primary_logo.alt_text || basics.logo_alt_text || basics.display_name || ""} src={basics.primary_logo.url} className={`${header.logo_size === "large" ? "h-14" : header.logo_size === "small" ? "h-8" : "h-10"} max-w-36 object-contain`} />}
            {header.display_mode !== "logo" && <div className="text-lg font-semibold" style={headingStyle}>{basics.display_name || webstore.name}</div>}
          </div>
        </header>
      )}
      {hero.show_hero !== false && (
        <section className="px-5 py-8" style={heroStyle} data-testid="branding-preview-hero">
          <div className="max-w-2xl">
            <h2 className="text-2xl font-semibold" style={{ fontFamily: headingFontFamily(colors.heading_font) }}>{hero.headline || basics.display_name || webstore.name}</h2>
            <p className="mt-2 text-sm opacity-90">{hero.supporting_text || basics.tagline}</p>
            {hero.primary_button_enabled && buttonHref && <a href={buttonHref} className="mt-4 inline-block border px-4 py-2 text-sm font-medium" style={buttonStyle}>{hero.primary_button_label || "Shop products"}</a>}
          </div>
        </section>
      )}
      {info.show_section !== false && (
        <section className="px-5 py-4" id="store-information" data-testid="branding-preview-store-information">
          <div className={info.supporting_image?.url ? "grid gap-4 sm:grid-cols-[120px_1fr]" : ""}>
            {info.supporting_image?.url && <img alt={info.supporting_image.alt_text || "Store information"} src={info.supporting_image.url} className="h-28 w-full rounded object-cover" />}
            <div>
              <h3 className="font-semibold" style={headingStyle}>{info.welcome_heading || `Welcome to ${basics.display_name || webstore.name}`}</h3>
              <p className="mt-1 text-sm">{info.welcome_text || info.store_instructions}</p>
              {info.store_instructions && <p className="mt-2 text-sm">{info.store_instructions}</p>}
              {info.contact_display !== "hidden" && <p className="mt-2 text-xs text-slate-500">{info.contact_display === "shop" ? "Contact the shop for questions." : "Contact the store organizer for questions."}</p>}
            </div>
          </div>
        </section>
      )}
      <TypeContentPreview storeType={webstore.store_type || "general"} content={branding.store_type_content || {}} />
      {catalog.show_catalog_area !== false && (
        <section className="px-5 py-4 border-t" id="catalog" style={{ backgroundColor: catalog.background_color || "#ffffff" }} data-testid="branding-preview-catalog">
          <h3 className="font-semibold" style={headingStyle}>{catalog.heading || "Featured products"}</h3>
          <p className="text-sm text-slate-600">{catalog.introduction || "Product catalog content is managed in a later Webstores stage."}</p>
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-2">
            {(products.length ? products : [{ id: "placeholder-1", name: "Product preview" }, { id: "placeholder-2", name: "Catalog item" }, { id: "placeholder-3", name: "Featured item" }]).slice(0, 3).map((product) => (
              <div key={product.id} className="rounded border bg-white p-3 text-sm">{product.name}</div>
            ))}
          </div>
        </section>
      )}
      {footer.show_footer !== false && (
        <footer className="px-5 py-4 text-sm" id="store-footer" style={{ backgroundColor: footer.background_color || "#0f172a", color: footer.text_color || "#ffffff" }} data-testid="branding-preview-footer">
          <div>{footer.display_mode === "logo" ? basics.logo_alt_text || basics.display_name : basics.display_name || webstore.name}</div>
          {footer.message && <div className="mt-1 opacity-85">{footer.message}</div>}
          {footer.show_contact && <div className="mt-2 text-xs opacity-80">Contact information will display from Store Setup.</div>}
          {footer.show_social_links && <div className="mt-2 text-xs opacity-80">Social links will display when configured.</div>}
          {footer.show_policy_links && <div className="mt-2 text-xs opacity-80">Store policy links will display when pages are available.</div>}
          {footer.show_powered_by && <div className="mt-2 text-xs opacity-70">Powered by SignGuy AI</div>}
        </footer>
      )}
    </div>
  );
}

export default function WebstoreBrandingEditor({ webstoreId, portal = false, products = [] }) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState("brand_basics");
  const [previewMode, setPreviewMode] = useState("desktop");
  const [note, setNote] = useState("");
  const queryKey = [portal ? "portal-webstore-branding" : "webstore-branding", webstoreId];
  const branding = useQuery({
    queryKey,
    queryFn: async () => {
      if (portal) {
        const r = await portalApi.get(`/portal/webstores/${webstoreId}/branding`);
        return r.data;
      }
      return getWebstoreBranding(webstoreId);
    },
    enabled: !!webstoreId,
  });
  const setupFiles = useQuery({
    queryKey: ["webstore-branding-setup-files", webstoreId],
    queryFn: () => listWebstoreSetupFiles(webstoreId),
    enabled: !!webstoreId,
  });
  const [draftOverride, setDraftOverride] = useState(null);
  const storedDraft = branding.data?.branding?.draft;
  const setupAwareDraft = useMemo(() => {
    const items = setupFiles.data?.items || setupFiles.data || [];
    const baseDraft = storedDraft || {};
    const activeFile = (category) => items.find((item) => item.status === "active" && item.category === category);
    const imageForFile = (file) => file ? {
      file_id: file.id,
      file_name: file.file_name,
      content_type: file.detected_content_type || file.content_type,
      ...(file.preview_url ? { url: file.preview_url } : {}),
    } : {};
    const logo = activeFile("logo");
    const banner = activeFile("banner");
    let next = baseDraft;
    if (logo && !baseDraft.brand_basics?.primary_logo?.file_id && !baseDraft.brand_basics?.primary_logo?.url) {
      next = setPath(next, "brand_basics.primary_logo", imageForFile(logo));
    }
    if (banner && !baseDraft.hero?.image?.file_id && !baseDraft.hero?.image?.url) {
      next = setPath(next, "hero.image", imageForFile(banner));
    }
    return next;
  }, [storedDraft, setupFiles.data]);
  const draft = draftOverride || setupAwareDraft;
  const webstore = branding.data?.webstore || {};
  const permissions = branding.data?.permissions || {};
  const validation = branding.data?.branding?.validation || { errors: [], warnings: [] };
  const invalidate = async () => {
    setDraftOverride(null);
    await qc.invalidateQueries({ queryKey });
  };
  const saveDraft = useMutation({
    mutationFn: () => portal
      ? portalApi.patch(`/portal/webstores/${webstoreId}/branding/draft`, { content: draft })
      : saveWebstoreBrandingDraft(webstoreId, draft),
    onSuccess: async () => { toast.success("Branding draft saved"); await invalidate(); },
    onError: (e) => toast.error(portal ? portalExtractError(e) : extractError(e)),
  });
  const requestReview = useMutation({
    mutationFn: () => portal
      ? portalApi.post(`/portal/webstores/${webstoreId}/branding/request-review`, { note })
      : requestWebstoreBrandingReview(webstoreId, note),
    onSuccess: async () => { toast.success("Owner review requested"); setNote(""); await invalidate(); },
    onError: (e) => toast.error(portal ? portalExtractError(e) : extractError(e)),
  });
  const approve = useMutation({
    mutationFn: () => portalApi.post(`/portal/webstores/${webstoreId}/branding/approve`, { note }),
    onSuccess: async () => { toast.success("Branding approved"); setNote(""); await invalidate(); },
    onError: (e) => toast.error(portalExtractError(e)),
  });
  const changes = useMutation({
    mutationFn: () => portalApi.post(`/portal/webstores/${webstoreId}/branding/request-changes`, { note }),
    onSuccess: async () => { toast.success("Changes requested"); setNote(""); await invalidate(); },
    onError: (e) => toast.error(portalExtractError(e)),
  });
  const publish = useMutation({
    mutationFn: () => publishWebstoreBranding(webstoreId),
    onSuccess: async () => { toast.success("Branding published"); await invalidate(); },
    onError: (e) => toast.error(extractError(e)),
  });
  const status = branding.data?.branding?.status || "draft";
  const selectedLabel = useMemo(() => CATEGORY_CARDS.find(([key]) => key === selected)?.[1] || "Brand Basics", [selected]);

  if (branding.isLoading) return <div className="text-sm text-muted-foreground">Loading branding...</div>;

  return (
    <div className="space-y-4" data-testid="webstore-branding-editor">
      <div className="rounded border bg-white p-2 flex flex-wrap items-center gap-2" data-testid="webstore-branding-ribbon">
        <Badge variant="outline">{statusLabel(status)}</Badge>
        <Button size="sm" variant="outline" onClick={() => saveDraft.mutate()} disabled={!permissions.can_save_draft || saveDraft.isPending}><Save className="size-4 mr-2" />Save Draft</Button>
        <Button size="sm" variant="outline" onClick={() => setPreviewMode(previewMode === "desktop" ? "mobile" : "desktop")}><Eye className="size-4 mr-2" />Preview</Button>
        <Button size="sm" variant="outline" disabled={!branding.data?.branding?.feedback_note} onClick={() => document.querySelector("[data-testid='branding-feedback']")?.scrollIntoView({ block: "center" })}><MessageSquare className="size-4 mr-2" />View Feedback</Button>
        {permissions.can_request_review && <Button size="sm" onClick={() => requestReview.mutate()} disabled={requestReview.isPending}><Send className="size-4 mr-2" />Request Owner Review</Button>}
        {permissions.can_owner_decide && <Button size="sm" onClick={() => approve.mutate()} disabled={approve.isPending || status !== "waiting_owner_approval"}><CheckCircle2 className="size-4 mr-2" />Approve</Button>}
        {permissions.can_owner_decide && <Button size="sm" variant="outline" onClick={() => changes.mutate()} disabled={changes.isPending || !note || status !== "waiting_owner_approval"}><MessageSquare className="size-4 mr-2" />Request Changes</Button>}
        {permissions.can_publish && <Button size="sm" onClick={() => publish.mutate()} disabled={publish.isPending || status !== "owner_approved"}><Rocket className="size-4 mr-2" />Publish</Button>}
      </div>

      {branding.data?.branding?.feedback_note && (
        <Card data-testid="branding-feedback"><CardContent className="p-3 text-sm">Feedback: {branding.data.branding.feedback_note}</CardContent></Card>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(360px,520px)] gap-4">
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2" data-testid="branding-category-cards">
            {CATEGORY_CARDS.map(([key, label]) => (
              <button key={key} type="button" onClick={() => setSelected(key)} className={`rounded border p-3 text-left text-sm ${selected === key ? "border-blue-500 bg-blue-50" : "bg-white hover:bg-slate-50"}`}>
                {label}
              </button>
            ))}
          </div>
          <Card>
            <CardHeader><CardTitle className="text-base">{selectedLabel}</CardTitle></CardHeader>
            <CardContent className="grid gap-3">
              <CategoryControls
                category={selected}
                draft={draft}
                onDraft={setDraftOverride}
                permissions={permissions}
                portal={portal}
                webstoreId={webstoreId}
                storeType={webstore.store_type || "general"}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">Review note</CardTitle></CardHeader>
            <CardContent><Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional note or owner feedback" data-testid="branding-review-note" /></CardContent>
          </Card>
        </div>
        <div className="space-y-4">
          {(validation.errors || []).length > 0 && <div className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" data-testid="branding-validation-errors">{validation.errors.join(" ")}</div>}
          {(validation.warnings || []).length > 0 && <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800" data-testid="branding-validation-warnings">{validation.warnings.join(" ")}</div>}
          <div className="flex gap-2">
            <Button size="sm" variant={previewMode === "desktop" ? "default" : "outline"} onClick={() => setPreviewMode("desktop")}>Desktop</Button>
            <Button size="sm" variant={previewMode === "mobile" ? "default" : "outline"} onClick={() => setPreviewMode("mobile")}>Mobile</Button>
          </div>
          <WebstoreBrandingPreview branding={draft} webstore={webstore} products={products} compact={previewMode === "mobile"} draft />
          <Card>
            <CardHeader><CardTitle className="text-base">Published history</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm" data-testid="branding-history">
              {(branding.data?.history || []).map((version) => (
                <div key={version.id} className="flex items-center justify-between gap-3 rounded border p-2">
                  <span>Version {version.version}</span>
                  <span className="text-muted-foreground">{version.created_at || version.published_at}</span>
                </div>
              ))}
              {(branding.data?.history || []).length === 0 && <div className="text-muted-foreground">No published branding versions yet.</div>}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">Branding activity</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm" data-testid="branding-activity">
              {(branding.data?.activity || []).map((row) => (
                <div key={row.id} className="rounded border p-2">
                  <div className="font-medium">{row.summary}</div>
                  <div className="text-xs text-muted-foreground">{row.actor_email || row.actor_id || "Unknown"} - {row.created_at}</div>
                  {row.metadata?.note && <div className="mt-1 text-xs">Note: {row.metadata.note}</div>}
                </div>
              ))}
              {(branding.data?.activity || []).length === 0 && <div className="text-muted-foreground">No branding activity yet.</div>}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
