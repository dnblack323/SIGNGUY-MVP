import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useAuth } from "@/auth/AuthContext";
import { createAssistantConversation, getAssistantConversation, getAssistantPreferences, listAssistantConversations, sendAssistantMessage } from "@/lib/businessAssistant";
import useAssistantVoice from "./useAssistantVoice";

const Context = createContext(null);
const blank = (identity) => ({ identity, mode: "owner", message: "", conversationId: null, messages: [], sources: [], proposals: [], conversations: [], preferences: null, loading: false, ready: false, accessInvalidated: false });
const requestKey = () => window.crypto?.randomUUID?.() || `turn-${Date.now()}-${Math.random().toString(36).slice(2)}`;

export function AssistantProvider({ children }) {
  const { user, permissions } = useAuth();
  const identity = `${user?.tenant_id || ""}:${user?.id || ""}:${user?.role || ""}:${JSON.stringify(permissions || user?.permissions || [])}`;
  const [session, setSession] = useState(() => blank(identity));
  const [enabled, setEnabled] = useState(false);
  const epoch = useRef(0);
  const busy = useRef(false);
  const retry = useRef(null);
  const active = useRef(identity);
  const creating = useRef(null);
  const storageKey = `signguy.assistant.active:${user?.tenant_id}:${user?.id}`;
  const state = session.identity === identity ? session : blank(identity);

  useLayoutEffect(() => {
    active.current = identity;
    epoch.current += 1;
    busy.current = false;
    retry.current = null;
    creating.current = null;
    setSession(blank(identity));
    return () => { epoch.current += 1; busy.current = false; };
  }, [identity]);

  const patch = useCallback((values) => setSession((old) => old.identity === identity ? { ...old, ...values } : old), [identity]);
  const clearAccess = useCallback(() => patch({ messages: [], sources: [], proposals: [], message: "", accessInvalidated: true }), [patch]);
  const ensureConversation = async () => {
    if (state.conversationId) return state.conversationId;
    if (!creating.current) {
      creating.current = createAssistantConversation({ mode: state.mode }).then((convo) => {
        if (active.current !== identity) throw new Error("Assistant identity changed");
        patch({ conversationId: convo.id, conversations: [convo, ...state.conversations] });
        localStorage.setItem(storageKey, convo.id);
        return convo.id;
      }).finally(() => { if (active.current === identity) creating.current = null; });
    }
    return creating.current;
  };
  const refresh = async () => {
    if (!state.conversationId) return;
    let result;
    try { result = await getAssistantConversation(state.conversationId); }
    catch (err) { if (active.current === identity) { patch({ messages: [], sources: [], proposals: [] }); if ([401, 402, 403].includes(err?.response?.status)) clearAccess(); } throw err; }
    if (active.current !== identity) return;
    const latest = [...(result.messages || [])].reverse().find((m) => m.role === "assistant");
    patch({ messages: result.messages || [], sources: (latest?.metadata?.sources || []).filter((ref) => ref.route), proposals: result.proposals || [] });
  };
  const voice = useAssistantVoice(identity, { ensureConversation, refresh, clear: clearAccess });
  const activate = useCallback(() => setEnabled(true), []);
  const selectConversation = useCallback(async (id) => {
    if (busy.current) return;
    const current = ++epoch.current;
    let result;
    try { result = id ? await getAssistantConversation(id) : { messages: [] }; }
    catch (err) { if (active.current === identity && [401, 402, 403].includes(err?.response?.status)) clearAccess(); throw err; }
    if (current !== epoch.current || active.current !== identity) return;
    retry.current = null;
    const latestAnswer = [...(result.messages || [])].reverse().find((item) => item.role === "assistant");
    patch({ conversationId: id, messages: result.messages || [], sources: latestAnswer?.metadata?.sources || [], proposals: result.proposals || [] });
    if (id) localStorage.setItem(storageKey, id); else localStorage.removeItem(storageKey);
  }, [identity, patch, storageKey, clearAccess]);

  useEffect(() => {
    if (!enabled || !user?.id) return;
    let cancelled = false;
    Promise.all([listAssistantConversations(), getAssistantPreferences()]).then(async ([conversations, preferences]) => {
      if (cancelled) return;
      patch({ conversations, preferences });
      const saved = localStorage.getItem(storageKey);
      const selected = conversations.find((item) => item.id === saved)?.id || conversations[0]?.id;
      if (selected) await selectConversation(selected);
      if (!cancelled) patch({ ready: true });
    }).catch(() => { if (!cancelled) patch({ ready: true }); });
    return () => { cancelled = true; };
  }, [enabled, identity, patch, selectConversation, storageKey, user?.id]);

  const send = async (context) => {
    if (busy.current || state.accessInvalidated || !state.message.trim()) return;
    busy.current = true;
    patch({ loading: true });
    const generation = epoch.current;
    const valid = () => generation === epoch.current && identity === active.current;
    try {
      let baseline = state.messages;
      if (voice.hasSession()) {
        await voice.end();
        if (!valid()) return;
        baseline = (await getAssistantConversation(state.conversationId)).messages || [];
      }
      const id = await ensureConversation();
      if (!valid()) return;
      const fields = { message: state.message, mode: state.mode, conversation_id: id, context };
      const signature = JSON.stringify(fields);
      if (retry.current?.signature !== signature) retry.current = { signature, key: requestKey() };
      const result = await sendAssistantMessage({ ...fields, idempotency_key: retry.current.key });
      if (!valid()) return;
      patch({ messages: [...baseline.filter((m) => ![result.user_message.id, result.assistant_message.id].includes(m.id)), result.user_message, result.assistant_message], sources: result.sources || [], proposals: result.proposals || [], message: "" });
      retry.current = null;
    } catch (err) {
      if (valid() && [401, 402, 403].includes(err?.response?.status)) clearAccess();
      throw err;
    } finally {
      if (valid()) { busy.current = false; patch({ loading: false }); }
    }
  };
  const setter = (key) => (value) => setSession((old) => old.identity !== identity ? old : { ...old, [key]: typeof value === "function" ? value(old[key]) : value });
  const changeConversation = async (id) => { if (voice.hasSession()) await voice.end(); return selectConversation(id); };
  return <Context.Provider value={{ ...state, voice, activate, send, refresh, selectConversation: changeConversation, patch,
    setMode: setter("mode"), setMessage: setter("message"), setConversationId: setter("conversationId"),
    setMessages: setter("messages"), setSources: setter("sources"), setProposals: setter("proposals"), setLoading: setter("loading") }}>{children}</Context.Provider>;
}

export function AssistantBoundary({ children }) {
  const session = useContext(Context);
  return session ? children : <AssistantProvider>{children}</AssistantProvider>;
}

export function useAssistantSession() {
  const session = useContext(Context);
  if (!session) throw new Error("AssistantProvider is required");
  return session;
}
