import { cn } from "@/lib/utils";

export function PageHeader({ title, subtitle, actions, breadcrumb, className, testId = "page-header" }) {
  return (
    <div className={cn("flex flex-col gap-2", className)} data-testid={testId}>
      {breadcrumb && (
        <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground" data-testid="page-header-breadcrumb">
          {breadcrumb}
        </div>
      )}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-semibold tracking-tight" data-testid="page-header-title">{title}</h1>
          {subtitle && <div className="text-sm text-muted-foreground mt-1">{subtitle}</div>}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}
export default PageHeader;
