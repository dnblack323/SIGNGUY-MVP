import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Plus, Archive, RotateCcw, XCircle } from "lucide-react";
import { toast } from "sonner";
import { money, EXPENSE_STATE_TONE } from "@/lib/ec7";
import { parseDollarsToCents } from "@/lib/format";
import { useAuth } from "@/auth/AuthContext";

const PAYMENT_METHODS = ["cash", "check", "card", "ach", "bank_transfer", "wire", "other"];
const DEDUCTIBLE = ["unknown", "fully_deductible", "partially_deductible", "non_deductible", "personal", "capitalized", "not_applicable"];

function NewExpenseDialog({ categories, onCreated }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    expense_date: new Date().toISOString().slice(0, 10),
    category_key: "materials", description: "",
    amount_dollars: "", tax_dollars: "0",
    payment_method: "card", deductible_class: "unknown", reference: "",
    internal_notes: "",
  });
  const upd = (k) => (e) => setForm((f) => ({ ...f, [k]: e?.target ? e.target.value : e }));

  async function submit(e) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      await api.post("/expenses", {
        expense_date: form.expense_date,
        category_key: form.category_key,
        description: form.description,
        amount_cents: parseDollarsToCents(form.amount_dollars),
        tax_cents: parseDollarsToCents(form.tax_dollars),
        payment_method: form.payment_method,
        deductible_class: form.deductible_class,
        reference: form.reference || undefined,
        internal_notes: form.internal_notes || undefined,
      });
      toast.success("Expense created");
      setOpen(false);
      setForm((f) => ({ ...f, description: "", amount_dollars: "", tax_dollars: "0", reference: "", internal_notes: "" }));
      onCreated?.();
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button data-testid="expense-new-button"><Plus className="size-4 mr-1" />New expense</Button></DialogTrigger>
      <DialogContent className="sm:max-w-[540px]">
        <DialogHeader>
          <DialogTitle>New expense</DialogTitle>
          <DialogDescription>Record money the shop spent. Integer cents. Total = amount + tax.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Date*</Label><Input type="date" required value={form.expense_date} onChange={upd("expense_date")} data-testid="expense-date-input" /></div>
            <div className="grid gap-1.5"><Label>Category*</Label>
              <Select value={form.category_key} onValueChange={(v) => setForm((f) => ({ ...f, category_key: v }))}>
                <SelectTrigger data-testid="expense-category-select"><SelectValue /></SelectTrigger>
                <SelectContent>{categories.map((c) => <SelectItem key={c.key} value={c.key}>{c.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid gap-1.5"><Label>Description*</Label><Input required value={form.description} onChange={upd("description")} data-testid="expense-description-input" /></div>
          <div className="grid grid-cols-3 gap-3">
            <div className="grid gap-1.5"><Label>Amount*</Label><Input required inputMode="decimal" placeholder="0.00" value={form.amount_dollars} onChange={upd("amount_dollars")} data-testid="expense-amount-input" /></div>
            <div className="grid gap-1.5"><Label>Tax</Label><Input inputMode="decimal" placeholder="0.00" value={form.tax_dollars} onChange={upd("tax_dollars")} data-testid="expense-tax-input" /></div>
            <div className="grid gap-1.5"><Label>Method</Label>
              <Select value={form.payment_method} onValueChange={(v) => setForm((f) => ({ ...f, payment_method: v }))}>
                <SelectTrigger data-testid="expense-method-select"><SelectValue /></SelectTrigger>
                <SelectContent>{PAYMENT_METHODS.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Deductible class</Label>
              <Select value={form.deductible_class} onValueChange={(v) => setForm((f) => ({ ...f, deductible_class: v }))}>
                <SelectTrigger data-testid="expense-deductible-select"><SelectValue /></SelectTrigger>
                <SelectContent>{DEDUCTIBLE.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5"><Label>Reference</Label><Input value={form.reference} onChange={upd("reference")} placeholder="check# / last-4" /></div>
          </div>
          <div className="grid gap-1.5"><Label>Internal notes</Label><Textarea rows={2} value={form.internal_notes} onChange={upd("internal_notes")} /></div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy} data-testid="expense-submit-button">{busy ? "Saving…" : "Create"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function VoidDialog({ expenseId, onDone }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit() {
    if (!reason.trim() || busy) return;
    setBusy(true);
    try {
      await api.post(`/expenses/${expenseId}/void`, { reason });
      toast.success("Voided");
      setOpen(false); setReason("");
      onDone?.();
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button size="sm" variant="ghost" data-testid={`expense-void-${expenseId}`}><XCircle className="size-3.5" /></Button></DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Void expense?</DialogTitle><DialogDescription>Voided expenses stay viewable in reports but are excluded from active totals. Reason required.</DialogDescription></DialogHeader>
        <div className="grid gap-1.5"><Label>Reason</Label><Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="expense-void-reason" /></div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="destructive" disabled={busy || !reason.trim()} onClick={submit} data-testid="expense-void-confirm">Void</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function ExpensesPage() {
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("expense:write");
  const canArchive = hasPerm("expense:archive");
  const [state, setState] = useState("active");

  const cats = useQuery({ queryKey: ["expense-categories"], queryFn: async () => (await api.get("/expense-categories")).data });
  const list = useQuery({
    queryKey: ["expenses", state],
    queryFn: async () => (await api.get("/expenses", { params: { state, limit: 200 } })).data,
  });

  const archiveMut = useMutation({
    mutationFn: async (id) => (await api.post(`/expenses/${id}/archive`)).data,
    onSuccess: () => { toast.success("Archived"); qc.invalidateQueries({ queryKey: ["expenses"] }); },
    onError: (err) => toast.error(extractError(err)),
  });
  const restoreMut = useMutation({
    mutationFn: async (id) => (await api.post(`/expenses/${id}/restore`)).data,
    onSuccess: () => { toast.success("Restored"); qc.invalidateQueries({ queryKey: ["expenses"] }); },
    onError: (err) => toast.error(extractError(err)),
  });

  const items = list.data?.items || [];
  const categories = cats.data?.items || [];

  return (
    <div className="space-y-4" data-testid="expenses-page">
      <PageHeader
        title="Expenses"
        subtitle="Operational shop spending. Integer cents. Historical rows preserved — category renames never rewrite past labels."
        actions={canWrite && categories.length > 0 && <NewExpenseDialog categories={categories} onCreated={() => qc.invalidateQueries({ queryKey: ["expenses"] })} />}
      />
      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">Show:</span>
        {["active", "archived", "voided"].map((k) => (
          <button
            key={k}
            onClick={() => setState(k)}
            data-testid={`expenses-state-${k}`}
            className={`px-2.5 py-1 rounded-md text-xs font-medium ${state === k ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/70"}`}
          >{k}</button>
        ))}
      </div>
      <div className="rounded-xl border bg-card overflow-hidden">
        <Table data-testid="expenses-table">
          <TableHeader>
            <TableRow>
              <TableHead>#</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Vendor</TableHead>
              <TableHead>Description</TableHead>
              <TableHead className="text-right">Amount</TableHead>
              <TableHead className="text-right">Tax</TableHead>
              <TableHead className="text-right">Total</TableHead>
              <TableHead>Method</TableHead>
              <TableHead>State</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {list.isLoading ? (
              <TableRow><TableCell colSpan={11} className="text-sm text-muted-foreground text-center py-8">Loading…</TableCell></TableRow>
            ) : items.length === 0 ? (
              <TableRow><TableCell colSpan={11} className="text-sm text-muted-foreground text-center py-8">No {state} expenses.</TableCell></TableRow>
            ) : items.map((e) => (
              <TableRow key={e.id} data-testid={`expense-row-${e.id}`}>
                <TableCell className="text-sm">#{e.number}</TableCell>
                <TableCell className="text-sm">{e.expense_date}</TableCell>
                <TableCell className="text-sm">{e.category_label_snapshot}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{e.vendor_name_snapshot || "—"}</TableCell>
                <TableCell className="text-sm max-w-[280px] truncate" title={e.description}>{e.description}</TableCell>
                <TableCell className="text-sm text-right">{money(e.amount_cents)}</TableCell>
                <TableCell className="text-sm text-right">{money(e.tax_cents)}</TableCell>
                <TableCell className="text-sm text-right font-medium">{money(e.total_cents)}</TableCell>
                <TableCell className="text-xs">{e.payment_method}</TableCell>
                <TableCell><Badge className={EXPENSE_STATE_TONE[e.state] || ""}>{e.state}</Badge></TableCell>
                <TableCell className="text-right">
                  {canArchive && e.state === "active" && (
                    <>
                      <Button size="sm" variant="ghost" onClick={() => archiveMut.mutate(e.id)} data-testid={`expense-archive-${e.id}`}><Archive className="size-3.5" /></Button>
                      <VoidDialog expenseId={e.id} onDone={() => qc.invalidateQueries({ queryKey: ["expenses"] })} />
                    </>
                  )}
                  {canArchive && e.state === "archived" && (
                    <Button size="sm" variant="ghost" onClick={() => restoreMut.mutate(e.id)} data-testid={`expense-restore-${e.id}`}><RotateCcw className="size-3.5" /></Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
