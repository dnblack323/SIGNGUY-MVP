import "@/App.css";
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/auth/AuthContext";
import RequireAuth from "@/auth/RequireAuth";
import AppShell from "@/components/app-shell/AppShell";
import LoginPage from "@/pages/LoginPage";
import RegisterTenantPage from "@/pages/RegisterTenantPage";
import ForgotPasswordPage from "@/pages/ForgotPasswordPage";
import ResetPasswordPage from "@/pages/ResetPasswordPage";
import DashboardPage from "@/pages/DashboardPage";
import CustomersPage from "@/pages/CustomersPage";
import CustomerDetailPage from "@/pages/CustomerDetailPage";
import QuotesPage from "@/pages/QuotesPage";
import QuoteDetailPage from "@/pages/QuoteDetailPage";
import OrdersPage from "@/pages/OrdersPage";
import OrderDetailPage from "@/pages/OrderDetailPage";
import WorkOrdersPage from "@/pages/WorkOrdersPage";
import WorkOrderDetailPage from "@/pages/WorkOrderDetailPage";
import ProductionBoardPage from "@/pages/ProductionBoardPage";
import PortalApp from "@/portal/PortalApp";
import PublicApp from "@/public/PublicApp";
import InvoicesPage from "@/pages/InvoicesPage";
import InvoiceDetailPage from "@/pages/InvoiceDetailPage";
import DocumentsPage from "@/pages/DocumentsPage";
import EmailHistoryPage from "@/pages/EmailHistoryPage";
import SettingsPage from "@/pages/SettingsPage";
import CompanySettingsPage from "@/pages/CompanySettingsPage";
import IntegrationsPage from "@/pages/IntegrationsPage";
import FeatureAccessPage from "@/pages/FeatureAccessPage";
import DataSecurityPage from "@/pages/DataSecurityPage";
import NotFoundPage from "@/pages/NotFoundPage";
import PricingFoundationPage from "@/pages/PricingFoundationPage";
import PricingCalculatorPage from "@/pages/PricingCalculatorPage";
import InventoryPage from "@/pages/InventoryPage";
import MaterialDetailPage from "@/pages/MaterialDetailPage";
import SupplyCenterPage from "@/pages/SupplyCenterPage";
import PurchaseOrdersPage from "@/pages/PurchaseOrdersPage";
import PurchaseOrderDetailPage from "@/pages/PurchaseOrderDetailPage";
import VendorDetailPage from "@/pages/VendorDetailPage";
import ExpensesPage from "@/pages/ExpensesPage";
import FinanceDashboardPage from "@/pages/FinanceDashboardPage";
import TaxReportsPage from "@/pages/TaxReportsPage";
import ReportsPage from "@/pages/ReportsPage";
import TeamDashboardPage from "@/pages/TeamDashboardPage";
import EmployeesPage from "@/pages/EmployeesPage";
import EmployeeDetailPage from "@/pages/EmployeeDetailPage";
import AnnouncementsPage from "@/pages/AnnouncementsPage";
import TimeClockPage from "@/pages/TimeClockPage";
import TimesheetsPage from "@/pages/TimesheetsPage";
import TeamSchedulePage from "@/pages/TeamSchedulePage";
import PayrollPage from "@/pages/PayrollPage";
import EmployeePortalAccessPage from "@/pages/EmployeePortalAccessPage";
import EmployeePortalApp from "@/portal/employee/EmployeePortalApp";
import { Toaster } from "sonner";

function LoggedInHome() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to="/" replace />;
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterTenantPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/portal/employee/*" element={<EmployeePortalApp />} />
          <Route path="/portal/*" element={<PortalApp />} />
          <Route path="/p/*" element={<PublicApp />} />
          <Route element={<RequireAuth><AppShell /></RequireAuth>}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/customers" element={<CustomersPage />} />
            <Route path="/customers/:id" element={<CustomerDetailPage />} />
            <Route path="/quotes" element={<QuotesPage />} />
            <Route path="/quotes/:id" element={<QuoteDetailPage />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/orders/:id" element={<OrderDetailPage />} />
            <Route path="/work-orders" element={<WorkOrdersPage />} />
            <Route path="/work-orders/board" element={<ProductionBoardPage />} />
            <Route path="/work-orders/:id" element={<WorkOrderDetailPage />} />
            <Route path="/invoices" element={<InvoicesPage />} />
            <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/email-history" element={<EmailHistoryPage />} />
            <Route path="/pricing-foundation" element={<PricingFoundationPage />} />
            <Route path="/pricing-calculator" element={<PricingCalculatorPage />} />
            <Route path="/inventory" element={<InventoryPage />} />
            <Route path="/materials/:id" element={<MaterialDetailPage />} />
            <Route path="/supply-center" element={<SupplyCenterPage />} />
            <Route path="/purchase-orders" element={<PurchaseOrdersPage />} />
            <Route path="/purchase-orders/:id" element={<PurchaseOrderDetailPage />} />
            <Route path="/vendors/:id" element={<VendorDetailPage />} />
            <Route path="/expenses" element={<ExpensesPage />} />
            <Route path="/finance" element={<FinanceDashboardPage />} />
            <Route path="/tax" element={<TaxReportsPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/team" element={<TeamDashboardPage />} />
            <Route path="/team/employees" element={<EmployeesPage />} />
            <Route path="/team/employees/:id" element={<EmployeeDetailPage />} />
            <Route path="/team/announcements" element={<AnnouncementsPage />} />
            <Route path="/team/schedule" element={<TeamSchedulePage />} />
            <Route path="/team/employee-portal" element={<EmployeePortalAccessPage />} />
            <Route path="/team/time-clock" element={<TimeClockPage />} />
            <Route path="/team/timesheets" element={<TimesheetsPage />} />
            <Route path="/team/payroll" element={<PayrollPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/settings/company" element={<CompanySettingsPage />} />
            <Route path="/settings/integrations" element={<IntegrationsPage />} />
            <Route path="/settings/features" element={<FeatureAccessPage />} />
            <Route path="/settings/data-security" element={<DataSecurityPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
          <Route path="*" element={<LoggedInHome />} />
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="top-right" />
    </AuthProvider>
  );
}

export default App;
