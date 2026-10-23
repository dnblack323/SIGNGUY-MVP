import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { deleteAssistantMemory, editAssistantMemory, saveAssistantMemory } from "@/lib/businessAssistant";
import { extractError } from "@/lib/api";

export default function MemoryManager({ items, context, onChanged, suggestion }) {
  const [editing, setEditing] = useState(null);
  const [topic, setTopic] = useState("");
  const [content, setContent] = useState("");
  const [approved, setApproved] = useState(false);
  const [linkSource, setLinkSource] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [suggestedSource, setSuggestedSource] = useState(null);
  useEffect(() => {
    if (!suggestion) return;
    const existing = items.find((item) => item.memory_key === suggestion.memory_key.trim().toLowerCase());
    setEditing(existing || null); setTopic(suggestion.memory_key); setContent(suggestion.content_text);
    setSuggestedSource(suggestion.source_type ? { source_type: suggestion.source_type, source_id: suggestion.source_id } : null);
    setApproved(false); setLinkSource(false);
    // Only a deliberate review click loads a suggestion; list refresh must not overwrite edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggestion]);
  const clear = () => { setEditing(null); setTopic(""); setContent(""); setApproved(false); setLinkSource(false); setSuggestedSource(null); };
  const save = async () => {
    if (!approved || busy) return;
    setBusy(true); setError("");
    try {
      const fields = { memory_key: topic, content_text: content, ...(!editing && (suggestedSource || (linkSource ? { source_type: context.source_entity_type, source_id: context.source_entity_id } : {}))) };
      if (editing) await editAssistantMemory(editing.id, { ...fields, expected_updated_at: editing.updated_at });
      else await saveAssistantMemory(fields);
      clear(); await onChanged();
    } catch (err) { setError(extractError(err, "Unable to save approved memory")); }
    finally { setBusy(false); }
  };
  const remove = async (id) => {
    if (busy) return;
    setBusy(true); setError("");
    try { await deleteAssistantMemory(id); if (editing?.id === id) clear(); await onChanged(); }
    catch (err) { setError(extractError(err, "Unable to delete memory")); }
    finally { setBusy(false); }
  };
  return <div className="space-y-3" data-testid="assistant-memory">
    <p className="text-sm">Private to you in this shop. Save approved preferences or background only. Current balances, Order status and schedules are always read from application records. Conversations are not automatically saved as memory.</p>
    {suggestion && <p>Conversational suggestion only. Review the exact text and approve before saving.</p>}
    <label className="block">Memory topic<Input aria-label="Memory topic" value={topic} onChange={(e) => setTopic(e.target.value)} maxLength={80} placeholder="e.g. update format" /></label>
    <label className="block">Approved context<Textarea aria-label="Memory content" value={content} onChange={(e) => setContent(e.target.value)} maxLength={1000} /></label>
    {context?.source_entity_type && !editing && <label className="block text-sm"><input type="checkbox" checked={linkSource} onChange={(e) => setLinkSource(e.target.checked)} /> Link to current {context.source_entity_type} record</label>}
    {(editing?.source_type || suggestedSource?.source_type) && <p>Source: {editing?.source_type || suggestedSource?.source_type}. Access is checked whenever this memory is used.</p>}
    <label className="block text-sm"><input type="checkbox" checked={approved} onChange={(e) => setApproved(e.target.checked)} /> I approve saving this private context. Saving an existing topic replaces its previous content.</label>
    <Button onClick={save} disabled={busy || !approved || !topic.trim() || !content.trim()}>{editing ? "Save memory correction" : "Approve and save memory"}</Button>
    {editing && <Button variant="outline" disabled={busy} onClick={clear}>Cancel memory edit</Button>}
    {error && <p role="alert">{error}</p>}
    {items.length ? items.map((item) => <div className="rounded border p-2 text-sm" key={item.id}><strong>{item.memory_key}</strong><p>{item.content_text}</p><Button size="sm" variant="outline" disabled={busy} onClick={() => { setEditing(item); setSuggestedSource(null); setTopic(item.memory_key); setContent(item.content_text); setApproved(false); }}>Edit memory</Button><Button size="sm" variant="outline" disabled={busy} onClick={() => remove(item.id)}>Delete memory</Button></div>) : <p className="text-sm">No retained memory.</p>}
  </div>;
}
