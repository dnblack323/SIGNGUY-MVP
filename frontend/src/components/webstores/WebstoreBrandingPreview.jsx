import { buttonRadius, headingFontFamily, overlayColor, safeDestination, TYPE_LABELS } from "./WebstoreBrandingUtils";

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
