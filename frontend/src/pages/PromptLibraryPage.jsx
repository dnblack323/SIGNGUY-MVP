import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/auth/AuthContext";
import { extractError } from "@/lib/api";
import { createPromptEntry, listPromptEntries, publishPromptEntry } from "@/lib/aiStudio";
import { Library } from "lucide-react";

export default function PromptLibraryPage() {
  const { hasPerm } = useAuth();
  const [prompts, setPrompts] = useState([]);
  const [form, setForm] = useState({ tool_key: "content_writer", mode_key: "business_copy", name: "", template: "" });
  const [error, setError] = useState("");

  const load = useCallback(() => {
    if (!hasPerm("ai_prompt:read")) return;
    listPromptEntries().then(setPrompts).catch((err) => setError(extractError(err, "Unable to load prompts")));
  }, [hasPerm]);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    setError("");
    try {
      const created = await createPromptEntry(form);
      await publishPromptEntry(created.id);
      setForm({ ...form, name: "", template: "" });
      load();
    } catch (err) {
      setError(extractError(err, "Unable to save prompt"));
    }
  };

  if (!hasPerm("ai_prompt:read")) {
    return (
      <div className="space-y-4" data-testid="prompt-library-page">
        <PageHeader title="Prompt Library" subtitle="Reusable AI prompts." />
        <Alert><Library className="size-4" /><AlertTitle>Access required</AlertTitle><AlertDescription>Prompt read access is required.</AlertDescription></Alert>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="prompt-library-page">
      <PageHeader title="Prompt Library" subtitle="Starter and tenant prompts with immutable published versions." />
      {error && <Alert variant="destructive"><AlertTitle>Prompt Library</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
      {hasPerm("ai_prompt:write") && (
        <Card>
          <CardHeader><CardTitle className="text-base">New Prompt</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-2"><Label>Name</Label><Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></div>
              <div className="space-y-2"><Label>Tool / Mode</Label><Input value={`${form.tool_key} / ${form.mode_key}`} onChange={() => {}} readOnly /></div>
            </div>
            <div className="space-y-2"><Label>Template</Label><Textarea rows={5} value={form.template} onChange={(event) => setForm({ ...form, template: event.target.value })} /></div>
            <Button size="sm" onClick={save}>Publish Prompt</Button>
          </CardContent>
        </Card>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {prompts.length === 0 ? <div className="text-sm text-muted-foreground" data-testid="prompt-library-empty">No tenant prompts saved yet.</div> : prompts.map((prompt) => (
          <Card key={prompt.id}>
            <CardHeader><CardTitle className="text-base flex items-center justify-between gap-3"><span>{prompt.name}</span><Badge variant="outline">{prompt.status}</Badge></CardTitle></CardHeader>
            <CardContent className="text-sm text-muted-foreground space-y-1">
              <div>{prompt.tool_key?.replace(/_/g, " ")} / {prompt.mode_key?.replace(/_/g, " ")}</div>
              <div>{prompt.description || "No description"}</div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
