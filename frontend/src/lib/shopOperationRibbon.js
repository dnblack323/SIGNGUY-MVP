import {
  CalendarDays,
  CheckCircle2,
  Clock,
  DollarSign,
  FileText,
  Filter,
  Plus,
  UserPlus,
  Users,
} from "lucide-react";

export const ORDER_STATUS_FILTERS = [
  { value: "all", label: "All" },
  { value: "draft", label: "Draft" },
  { value: "confirmed", label: "Confirmed" },
  { value: "in_production", label: "Production" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

export const ORDER_SOURCE_FILTER_FALLBACK = [
  { value: "manual", label: "Manual" },
  { value: "quote", label: "Quote" },
  { value: "webstore", label: "Webstore" },
  { value: "wrap_lab", label: "Wrap Lab" },
  { value: "legacy_unknown", label: "Legacy / Unknown" },
];

function navCommand({ id, label, icon, to, permission, tooltip, responsivePriority }) {
  return { id, label, icon, to, permission, tooltip, responsivePriority };
}

export function createCommands({ onNewOrder, onNewCustomer, canCreateOrder, canCreateCustomer }) {
  return [
    {
      id: "new-order",
      label: "New Order",
      icon: Plus,
      permission: "order:write",
      onSelect: onNewOrder,
      to: onNewOrder ? undefined : "/orders",
      disabled: !!onNewOrder && !canCreateOrder,
      disabledReason: "Order write permission required",
      tooltip: "Create a manual Order",
      responsivePriority: 1,
      testId: "ribbon-new-order",
    },
    navCommand({
      id: "new-quote",
      label: "New Quote",
      icon: FileText,
      to: "/quotes",
      permission: "quote:write",
      tooltip: "Open Quotes to create a Quote",
      responsivePriority: 2,
    }),
    {
      id: "new-customer",
      label: "New Customer",
      icon: UserPlus,
      permission: "customer:write",
      onSelect: onNewCustomer,
      to: onNewCustomer ? undefined : "/customers",
      disabled: !!onNewCustomer && !canCreateCustomer,
      disabledReason: "Customer write permission required",
      tooltip: "Add a customer",
      responsivePriority: 3,
      testId: "ribbon-new-customer",
    },
    navCommand({
      id: "pricing-calculator",
      label: "Pricing Calculator",
      icon: DollarSign,
      to: "/pricing-calculator",
      permission: "pricing:read",
      tooltip: "Open the pricing calculator",
      responsivePriority: 4,
    }),
  ];
}

export function workflowCommands() {
  return [
    navCommand({
      id: "new-task",
      label: "New Task",
      icon: CheckCircle2,
      to: "/team/tasks",
      permission: "task:read",
      tooltip: "Open Tasks",
      responsivePriority: 31,
    }),
    navCommand({
      id: "schedule-install",
      label: "Schedule Install",
      icon: Clock,
      to: "/shop-schedule",
      permission: "schedule:read",
      tooltip: "Open Shop Schedule",
      responsivePriority: 32,
    }),
    navCommand({
      id: "open-calendar",
      label: "Open Calendar",
      icon: CalendarDays,
      to: "/shop-schedule",
      permission: "schedule:read",
      tooltip: "Open calendar",
      responsivePriority: 33,
    }),
  ];
}

export function orderStatusCommands({ status, setStatus }) {
  return ORDER_STATUS_FILTERS.map((item, index) => ({
    id: `status-${item.value}`,
    label: item.label,
    icon: Filter,
    onSelect: () => setStatus(item.value),
    active: status === item.value,
    tooltip: `Show ${item.label.toLowerCase()} Orders`,
    responsivePriority: 10 + index,
    testId: `ribbon-order-status-${item.value}`,
  }));
}

export function orderSourceDropdown({ source, setSource, sourceFilters = ORDER_SOURCE_FILTER_FALLBACK }) {
  const sources = [{ value: "all", label: "All Orders" }, ...(sourceFilters || ORDER_SOURCE_FILTER_FALLBACK)];
  const active = sources.find((item) => item.value === source) || sources[0];
  return {
    id: "order-source",
    label: active.label === "All Orders" ? "Source" : active.label,
    icon: Filter,
    tooltip: "Filter Orders by canonical source",
    responsivePriority: 17,
    testId: "ribbon-order-source",
    children: sources.map((item) => ({
      id: `source-${item.value}`,
      label: item.label,
      icon: item.value === source ? CheckCircle2 : undefined,
      onSelect: () => setSource(item.value),
      active: source === item.value,
      testId: `ribbon-order-source-${item.value}`,
    })),
  };
}

export function buildOrdersRibbonGroups({ canWrite, onNewOrder, status, setStatus, source, setSource, sourceFilters }) {
  return [
    {
      id: "create",
      label: "Create",
      commands: createCommands({ onNewOrder, canCreateOrder: canWrite }),
    },
    {
      id: "status",
      label: "Status",
      commands: orderStatusCommands({ status, setStatus }),
    },
    {
      id: "source",
      label: "Source",
      commands: [orderSourceDropdown({ source, setSource, sourceFilters })],
    },
    {
      id: "workflow",
      label: "Workflow",
      commands: workflowCommands(),
    },
  ];
}

export function buildCustomersRibbonGroups({ canWrite, onNewCustomer }) {
  return [
    {
      id: "create",
      label: "Create",
      commands: createCommands({ onNewCustomer, canCreateCustomer: canWrite }),
    },
    {
      id: "workflow",
      label: "Workflow",
      commands: workflowCommands(),
    },
  ];
}

export function customerSearchCommandLabel(query) {
  return query ? `Search: ${query}` : "Search";
}

export { Users };
