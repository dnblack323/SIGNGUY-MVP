import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/auth/AuthContext";
import { extractError } from "@/lib/api";
import { getAIStudioCatalog, runAIStudioTool } from "@/lib/aiStudio";
import { FileText, Image, Library, Sparkles } from "lucide-react";

function FieldControl({ field, value, onChange }) {
  const id = `studio-field-${field.name}`;
  if (field.type === "textarea") {
    return (
      <div className="space-y-2">
        <Label htmlFor={id}>{field.label}</Label>
        <Textarea id={id} value={value || ""} onChange={(event) => onChange(field.name, event.target.value)} required={field.required} rows={4} />
      </div>
    );
  }
  if (field.type === "select") {
    return (
      <div className="space-y-2">
        <Label>{field.label}</Label>
        <Select value={value || ""} onValueChange={(next) => onChange(field.name, next)}>
          <SelectTrigger id={id}><SelectValue placeholder={field.label} /></SelectTrigger>
          <SelectContent>{(field.options || []).map((option) => <SelectItem key={option} value={option}>{option.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
        </Select>
      </div>
    );
  }
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{field.label}</Label>
      <Input id={id} value={value || ""} type={field.type === "number" ? "number" : "text"} onChange={(event) => onChange(field.name, event.target.value)} required={field.required} />
    </div>
  );
}

function Pill({ children }) {
  return <Badge variant="outline" className="rounded-md">{children}</Badge>;
}

export default function AIStudioPage() {
  const { hasPerm } = useAuth();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [catalog, setCatalog] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedFamily, setSelectedFamily] = useState("design_image");
  const [selectedTool, setSelectedTool] = useState(searchParams.get("tool") || "ai_image_generator");
  const [selectedMode, setSelectedMode] = useState(searchParams.get("mode") || "general_text_to_image");
  const [inputs, setInputs] = useState({ publicity_permission_state: "unknown" });
  const [result, setResult] = useState(null);

  useEffect(() => {
    let active = true;
    getAIStudioCatalog().then((data) => {
      if (!active) return;
      setCatalog(data);
      const familyFromPath = location.pathname.endsWith("/marketing-brand") ? "marketing_brand"
        : location.pathname.endsWith("/writing-documents") ? "writing_documents"
          : location.pathname.endsWith("/pricing-profitability") ? "pricing_profitability"
            : "design_image";
      const requestedTool = searchParams.get("tool") || "ai_image_generator";
      const tool = data.tools.find((item) => item.tool_key === requestedTool)
        || data.tools.find((item) => item.family_key === familyFromPath)
        || data.tools[0];
      setSelectedFamily(tool.family_key || familyFromPath);
      setSelectedTool(tool.tool_key);
      setSelectedMode(searchParams.get("mode") || tool.modes[0]?.mode_key);
    }).catch((err) => setError(extractError(err, "Unable to load AI Studio catalog")));
    return () => { active = false; };
  }, [location.pathname, searchParams]);

  const families = catalog?.families || [];
  const tools = useMemo(() => (catalog?.tools || []).filter((tool) => tool.family_key === selectedFamily), [catalog, selectedFamily]);
  const tool = useMemo(() => (catalog?.tools || []).find((item) => item.tool_key === selectedTool), [catalog, selectedTool]);
  const mode = useMemo(() => (tool?.modes || []).find((item) => item.mode_key === selectedMode) || tool?.modes?.[0], [tool, selectedMode]);

  const chooseFamily = (familyKey) => {
    setSelectedFamily(familyKey);
    const firstTool = (catalog?.tools || []).find((item) => item.family_key === familyKey);
    setSelectedTool(firstTool?.tool_key || "");
    setSelectedMode(firstTool?.modes?.[0]?.mode_key || "");
    setInputs({ publicity_permission_state: "unknown" });
    setResult(null);
  };

  const chooseTool = (toolKey) => {
    const nextTool = (catalog?.tools || []).find((item) => item.tool_key === toolKey);
    setSelectedTool(toolKey);
    setSelectedMode(nextTool?.modes?.[0]?.mode_key || "");
    setInputs({ publicity_permission_state: "unknown" });
    setResult(null);
  };

  const onRun = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const payload = {
        tool_key: selectedTool,
        mode_key: selectedMode,
        inputs,
        context: {
          context_type: searchParams.get("context_type") || undefined,
          context_id: searchParams.get("context_id") || undefined,
          publicity_permission_state: inputs.publicity_permission_state,
        },
        idempotency_key: `${selectedTool}:${selectedMode}:${Date.now()}`,
      };
      setResult(await runAIStudioTool(payload));
    } catch (err) {
      setError(extractError(err, "Unable to run AI Studio tool"));
    } finally {
      setLoading(false);
    }
  };

  if (!hasPerm("ai_tool:use")) {
    return (
      <div className="space-y-4" data-testid="ai-studio-page">
        <PageHeader title="AI Studio" subtitle="Studio tools for design, writing, marketing, and pricing." />
        <Alert><Sparkles className="size-4" /><AlertTitle>Access required</AlertTitle><AlertDescription>Your account does not include AI tool access.</AlertDescription></Alert>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="ai-studio-page">
      <PageHeader
        title="AI Studio"
        subtitle="AI credits apply"
        actions={(
          <>
            <Button asChild size="sm" variant="outline"><Link to="/studio/prompts"><Library className="size-4 mr-2" />Prompts</Link></Button>
            <Button asChild size="sm" variant="outline"><Link to="/studio/assets"><Image className="size-4 mr-2" />Assets</Link></Button>
            <Button asChild size="sm" variant="outline"><Link to="/studio/activity"><FileText className="size-4 mr-2" />Activity</Link></Button>
          </>
        )}
      />

      {error && <Alert variant="destructive" data-testid="ai-studio-error"><AlertTitle>AI Studio</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}

      {catalog && (
        <Card className="border-primary/30 bg-primary/5" data-testid="featured-image-generator">
          <CardHeader><CardTitle className="text-lg flex items-center gap-2"><Sparkles className="size-5" />AI Image Generator</CardTitle></CardHeader>
          <CardContent className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <div className="text-muted-foreground">General Text-to-Image and Custom Image Concept modes are ready for local mock generation.</div>
            <Button size="sm" onClick={() => { setSelectedFamily("design_image"); chooseTool("ai_image_generator"); }}>Open</Button>
          </CardContent>
        </Card>
      )}

      <Tabs value={selectedFamily} onValueChange={chooseFamily}>
        <TabsList className="grid grid-cols-2 lg:grid-cols-4 h-auto">
          {families.map((family) => <TabsTrigger key={family.family_key} value={family.family_key}>{family.name}</TabsTrigger>)}
        </TabsList>
        {families.map((family) => (
          <TabsContent key={family.family_key} value={family.family_key} className="space-y-4">
            <div className="grid grid-cols-1 xl:grid-cols-[280px_1fr] gap-4">
              <div className="rounded border divide-y">
                {tools.map((item) => (
                  <button key={item.tool_key} className={`w-full text-left p-3 hover:bg-muted ${selectedTool === item.tool_key ? "bg-muted" : ""}`} onClick={() => chooseTool(item.tool_key)} data-testid={`tool-${item.tool_key}`}>
                    <div className="font-medium">{item.name}</div>
                    <div className="text-xs text-muted-foreground">{item.modes.length} mode{item.modes.length === 1 ? "" : "s"}</div>
                  </button>
                ))}
              </div>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex flex-wrap items-center gap-2">
                    {tool?.name || "Tool"}
                    {mode && <Pill>{mode.usage_band}</Pill>}
                    <Pill>{mode?.credit_display || "AI credits apply"}</Pill>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-2">
                      <Label>Mode</Label>
                      <Select value={mode?.mode_key || ""} onValueChange={(next) => { setSelectedMode(next); setInputs({ publicity_permission_state: "unknown" }); setResult(null); }}>
                        <SelectTrigger data-testid="ai-mode-select"><SelectValue /></SelectTrigger>
                        <SelectContent>{(tool?.modes || []).map((item) => <SelectItem key={item.mode_key} value={item.mode_key}>{item.name}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Context</Label>
                      <Input readOnly value={searchParams.get("context_type") ? `${searchParams.get("context_type")} ${searchParams.get("context_id")}` : "None selected"} />
                    </div>
                  </div>

                  {(mode?.fields || []).map((field) => (
                    <FieldControl key={field.name} field={field} value={inputs[field.name]} onChange={(name, value) => setInputs((prev) => ({ ...prev, [name]: value }))} />
                  ))}

                  {(mode?.warnings || []).length > 0 && (
                    <Alert>
                      <AlertTitle>Boundary</AlertTitle>
                      <AlertDescription>{mode.warnings.join(" ")}</AlertDescription>
                    </Alert>
                  )}

                  <Button onClick={onRun} disabled={loading || !mode} data-testid="ai-run-tool">
                    <Sparkles className="size-4 mr-2" />{loading ? "Creating..." : "Create Draft"}
                  </Button>

                  {result && (
                    <div className="rounded border p-4 space-y-3" data-testid="ai-result">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge>{result.record_type?.replace(/_/g, " ")}</Badge>
                        <Badge variant="outline">{result.usage_band}</Badge>
                        <Badge variant="outline">{result.credit_display}</Badge>
                      </div>
                      <Textarea value={result.content_text || ""} readOnly rows={6} />
                      {(result.warnings || []).map((warning) => <div key={warning} className="text-sm text-amber-700">{warning}</div>)}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
