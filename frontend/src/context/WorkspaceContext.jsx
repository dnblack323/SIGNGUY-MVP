import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { detectWorkspaceTarget, pathFromWorkspace } from "@/lib/workspaceRoutes";

const WorkspaceContext = createContext(null);

const EMPTY_STATE = {
  open_workspaces: [],
  recent_workspaces: [],
  limits: { max_open: 8, max_recent: 20 },
};

function activeOf(items = []) {
  return items.find((item) => item.active) || items[0] || null;
}

export function WorkspaceProvider({ children }) {
  const [state, setState] = useState(EMPTY_STATE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [limitError, setLimitError] = useState(null);
  const [dirtyPrompt, setDirtyPrompt] = useState(null);
  const location = useLocation();
  const navigate = useNavigate();
  const lastRegisteredKey = useRef("");
  const scrollPatchTimer = useRef(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get("/workspaces");
      setState({ ...EMPTY_STATE, ...data });
    } catch (err) {
      setError(err?.response?.data?.detail || "Workspace Dock could not load.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const activeWorkspace = useMemo(() => activeOf(state.open_workspaces), [state.open_workspaces]);
  const hasDirtyWorkspace = useMemo(
    () => state.open_workspaces.some((workspace) => workspace.dirty),
    [state.open_workspaces],
  );

  const applyState = useCallback((data) => {
    setState({ ...EMPTY_STATE, ...data });
  }, []);

  const requestDirtyConfirmation = useCallback((workspace, action, message) => {
    if (!workspace?.dirty) {
      action();
      return;
    }
    setDirtyPrompt({ workspace, action, message });
  }, []);

  const confirmBeforeAbandon = useCallback((action, message = "You have unsaved workspace changes.") => {
    if (!hasDirtyWorkspace) {
      action();
      return;
    }
    setDirtyPrompt({ workspace: activeWorkspace, action, message });
  }, [activeWorkspace, hasDirtyWorkspace]);

  const registerCurrentRoute = useCallback(async () => {
    const target = detectWorkspaceTarget(location);
    if (!target) return;
    const registrationKey = `${target.workspace_type}:${target.record_id || "default"}:${target.pathname}:${location.search}`;
    if (registrationKey === lastRegisteredKey.current) return;
    lastRegisteredKey.current = registrationKey;
    try {
      const { data } = await api.post("/workspaces/open", target);
      applyState(data);
      setError("");
      setLimitError(null);
    } catch (err) {
      if (err?.response?.status === 409) {
        setLimitError(err.response.data?.detail || { message: "Workspace limit reached" });
      } else {
        setError(err?.response?.data?.detail || "Workspace could not be opened.");
      }
    }
  }, [applyState, location]);

  useEffect(() => {
    registerCurrentRoute();
  }, [registerCurrentRoute]);

  const navigateToWorkspace = useCallback((workspace) => {
    navigate(pathFromWorkspace(workspace));
    window.setTimeout(() => {
      const y = Number(workspace?.scroll_position || workspace?.view_state?.scroll_y || 0);
      if (Number.isFinite(y) && y > 0) window.scrollTo({ top: y, behavior: "instant" });
    }, 50);
  }, [navigate]);

  const activate = useCallback(async (workspace) => {
    const run = async () => {
      try {
        const { data } = await api.post(`/workspaces/${workspace.id}/activate`);
        applyState(data);
        navigateToWorkspace(workspace);
      } catch (err) {
        setError(err?.response?.data?.detail || "Workspace could not be activated.");
      }
    };
    requestDirtyConfirmation(activeWorkspace, run, "Switching workspaces will leave unsaved changes behind.");
  }, [activeWorkspace, applyState, navigateToWorkspace, requestDirtyConfirmation]);

  const patchWorkspace = useCallback(async (workspaceId, updates) => {
    try {
      const { data } = await api.patch(`/workspaces/${workspaceId}`, updates);
      applyState(data);
    } catch (err) {
      setError(err?.response?.data?.detail || "Workspace state could not be saved.");
    }
  }, [applyState]);

  const setCurrentDirty = useCallback((dirty) => {
    if (!activeWorkspace?.id || activeWorkspace.dirty === dirty) return;
    patchWorkspace(activeWorkspace.id, { dirty });
  }, [activeWorkspace, patchWorkspace]);

  const close = useCallback(async (workspace) => {
    const run = async () => {
      try {
        const { data } = await api.post(`/workspaces/${workspace.id}/close`);
        applyState(data);
        const nextActive = activeOf(data.open_workspaces);
        if (workspace.active && nextActive) navigateToWorkspace(nextActive);
      } catch (err) {
        setError(err?.response?.data?.detail || "Workspace could not be closed.");
      }
    };
    requestDirtyConfirmation(workspace, run, "Close this workspace and discard unsaved local changes?");
  }, [applyState, navigateToWorkspace, requestDirtyConfirmation]);

  const pin = useCallback(async (workspace, pinned) => {
    try {
      const { data } = await api.post(`/workspaces/${workspace.id}/${pinned ? "pin" : "unpin"}`);
      applyState(data);
    } catch (err) {
      setError(err?.response?.data?.detail || "Workspace pin state could not be saved.");
    }
  }, [applyState]);

  const reorder = useCallback(async (workspaceIds) => {
    try {
      const { data } = await api.post("/workspaces/reorder", { workspace_ids: workspaceIds });
      applyState(data);
    } catch (err) {
      setError(err?.response?.data?.detail || "Workspace order could not be saved.");
    }
  }, [applyState]);

  const reopenRecent = useCallback(async (workspace) => {
    try {
      const { data } = await api.post(`/workspaces/recent/${workspace.id}/reopen`);
      applyState(data);
      navigateToWorkspace(workspace);
      setLimitError(null);
    } catch (err) {
      if (err?.response?.status === 409) {
        setLimitError(err.response.data?.detail || { message: "Workspace limit reached" });
      } else {
        setError(err?.response?.data?.detail || "Recent workspace could not be reopened.");
      }
    }
  }, [applyState, navigateToWorkspace]);

  const removeRecent = useCallback(async (workspace) => {
    try {
      const { data } = await api.delete(`/workspaces/recent/${workspace.id}`);
      applyState(data);
    } catch (err) {
      setError(err?.response?.data?.detail || "Recent workspace could not be removed.");
    }
  }, [applyState]);

  useEffect(() => {
    const onBeforeUnload = (event) => {
      if (!hasDirtyWorkspace) return undefined;
      event.preventDefault();
      event.returnValue = "";
      return "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [hasDirtyWorkspace]);

  useEffect(() => {
    const onScroll = () => {
      if (!activeWorkspace?.id) return;
      window.clearTimeout(scrollPatchTimer.current);
      scrollPatchTimer.current = window.setTimeout(() => {
        patchWorkspace(activeWorkspace.id, {
          scroll_position: Math.max(0, Math.round(window.scrollY || 0)),
          view_state: { ...activeWorkspace.view_state, scroll_y: Math.max(0, Math.round(window.scrollY || 0)) },
        });
      }, 800);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.clearTimeout(scrollPatchTimer.current);
    };
  }, [activeWorkspace, patchWorkspace]);

  const value = useMemo(() => ({
    ...state,
    loading,
    error,
    limitError,
    setLimitError,
    dirtyPrompt,
    setDirtyPrompt,
    activeWorkspace,
    hasDirtyWorkspace,
    refresh,
    activate,
    close,
    pin,
    reorder,
    reopenRecent,
    removeRecent,
    setCurrentDirty,
    confirmBeforeAbandon,
  }), [
    state,
    loading,
    error,
    limitError,
    dirtyPrompt,
    activeWorkspace,
    hasDirtyWorkspace,
    refresh,
    activate,
    close,
    pin,
    reorder,
    reopenRecent,
    removeRecent,
    setCurrentDirty,
    confirmBeforeAbandon,
  ]);

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) {
    throw new Error("useWorkspace must be used inside WorkspaceProvider");
  }
  return value;
}

export function useWorkspaceDirty(isDirty) {
  const context = useContext(WorkspaceContext);
  useEffect(() => {
    context?.setCurrentDirty(Boolean(isDirty));
  }, [context, isDirty]);
}
