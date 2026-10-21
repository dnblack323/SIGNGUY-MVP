import { useEffect, useState } from "react";
import { getAssistantPreferences, saveAssistantPreferences } from "@/lib/businessAssistant";
import { Button } from "@/components/ui/button";
import { AssistantBoundary, useAssistantSession } from "./AssistantSession";

function Settings() {
  const session = useAssistantSession();
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { let active = true; getAssistantPreferences().then((value) => { if (active) setData(value); }).catch(() => { if (active) setError("Unable to load Assistant Settings."); }); return () => { active = false; }; }, []);
  const save = async (updates) => {
    setBusy(true); setError("");
    try {
      const result = await saveAssistantPreferences(updates);
      setData(result); session.patch({ preferences: result });
    } catch { setError("Settings were not saved. Your previous selection is still active."); }
    finally { setBusy(false); }
  };
  return <section className="space-y-4" data-testid="assistant-settings">
    <h1 className="text-xl font-semibold">Assistant Settings</h1>
    <p className="text-sm">Personal preferences apply to your assistant conversations. Voice, permissions and customer communications are independent.</p>
    {error && <p role="alert">{error}</p>}
    {!data ? <p>Loading settings…</p> : <>
      <fieldset disabled={busy} className="grid gap-3 sm:grid-cols-2"><legend className="font-medium">Personality</legend>
        {data.options.map((option) => <label key={option.key} className="rounded border p-3 cursor-pointer">
          <input type="radio" name="assistant-personality" value={option.key} checked={data.preferences.personality_key === option.key} onChange={() => save({ personality_key: option.key })} />
          <span className="ml-2 font-medium">{option.name}</span><p>{option.tagline}</p><p className="text-sm text-muted-foreground">{option.description}</p>
        </label>)}
      </fieldset>
      <label className="block">Business timezone <input className="ml-2 rounded border p-2" aria-label="Business timezone" defaultValue={data.preferences.timezone} key={data.preferences.timezone} onBlur={(event) => { if (event.target.value !== data.preferences.timezone) save({ timezone: event.target.value }); }} disabled={busy} /></label>
      <label className="block">Response length <select className="ml-2 rounded border p-2" value={data.preferences.response_length} disabled={busy} onChange={(event) => save({ response_length: event.target.value })}><option value="concise">Concise</option><option value="detailed">Detailed</option></select></label>
      <p className="text-sm">Saved voice: {data.preferences.voice || "Not selected"}. Voice selection and preview are a later stage.</p>
      <Button variant="outline" onClick={() => save({})} disabled={busy}>{busy ? "Saving…" : "Refresh saved preferences"}</Button>
    </>}
  </section>;
}

function PrivateSettings() {
  const session = useAssistantSession();
  return <Settings key={session.identity} />;
}

export default function AssistantSettings() { return <AssistantBoundary><PrivateSettings /></AssistantBoundary>; }
