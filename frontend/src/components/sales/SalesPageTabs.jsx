import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

const SALES_TABS = [
  { label: "Intake", to: "/intake", testId: "sales-tab-intake" },
  { label: "Customers", to: "/customers", testId: "sales-tab-customers" },
  { label: "Quotes", to: "/quotes", testId: "sales-tab-quotes" },
  { label: "Orders", to: "/orders", testId: "sales-tab-orders" },
];

export default function SalesPageTabs() {
  return (
    <nav
      className="flex flex-wrap items-center gap-1 rounded-lg border bg-card p-1"
      aria-label="Sales pages"
      data-testid="sales-page-tabs"
    >
      {SALES_TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          data-testid={tab.testId}
          className={({ isActive }) => cn(
            "h-8 rounded-md px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            isActive ? "bg-slate-950 text-white shadow-sm" : "text-muted-foreground hover:bg-muted hover:text-foreground",
          )}
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
