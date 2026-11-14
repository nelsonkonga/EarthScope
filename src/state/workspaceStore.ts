import { create } from "zustand";
import { reduceAssistantActions, type CatalogIndex, type SessionSlice } from "../domain/actions";
import type { ActionResult, Comparison, PanelId } from "../domain/types";

type WorkspaceState = SessionSlice & {
  playbackSpeed: 1 | 2 | 4;
  expandedChartVariableId: string | null;
  notice: string | null;
  assistantSessionId: string | null;
  selectionNonce: number;
  selectZone: (id: string) => void;
  closeCard: () => void;
  toggleVariable: (id: string) => void;
  clearVariables: () => void;
  setPrimary: (id: string) => void;
  removeVariable: (id: string) => void;
  setDate: (date: string) => void;
  setPlayback: (playback: "paused" | "playing") => void;
  setSpeed: (speed: 1 | 2 | 4) => void;
  setPanel: (panel: PanelId | null) => void;
  togglePanel: (panel: PanelId) => void;
  setExpandedChart: (id: string | null) => void;
  setComparison: (comparison: Comparison | null) => void;
  setNotice: (notice: string | null) => void;
  setAssistantSessionId: (id: string | null) => void;
  ensureDate: (date: string) => void;
  applyAssistant: (actions: unknown[], catalog: CatalogIndex) => ActionResult[];
};

const initial: SessionSlice = {
  selectedZoneId: null,
  activeVariableIds: [],
  primaryVariableId: null,
  selectedDate: null,
  playback: "paused",
  activePanel: null,
  zoneCardOpen: false,
  comparison: null,
};

export const useWorkspace = create<WorkspaceState>((set, get) => ({
  ...initial,
  playbackSpeed: 1,
  expandedChartVariableId: null,
  notice: null,
  assistantSessionId: null,
  selectionNonce: 0,
  selectZone: (id) =>
    set((state) => ({
      selectedZoneId: id,
      zoneCardOpen: true,
      selectionNonce: state.selectionNonce + 1,
    })),
  closeCard: () => set({ zoneCardOpen: false }),
  toggleVariable: (id) =>
    set((state) => {
      const exists = state.activeVariableIds.includes(id);
      const activeVariableIds = exists
        ? state.activeVariableIds.filter((item) => item !== id)
        : [...state.activeVariableIds, id];
      const primaryVariableId =
        state.primaryVariableId && activeVariableIds.includes(state.primaryVariableId)
          ? state.primaryVariableId
          : (activeVariableIds[0] ?? null);
      return { activeVariableIds, primaryVariableId, playback: "paused" };
    }),
  clearVariables: () => set({ activeVariableIds: [], primaryVariableId: null, playback: "paused" }),
  setPrimary: (id) =>
    set((state) => (state.activeVariableIds.includes(id) ? { primaryVariableId: id } : state)),
  removeVariable: (id) =>
    set((state) => {
      const activeVariableIds = state.activeVariableIds.filter((item) => item !== id);
      const primaryVariableId =
        state.primaryVariableId === id ? (activeVariableIds[0] ?? null) : state.primaryVariableId;
      return { activeVariableIds, primaryVariableId, playback: "paused" };
    }),
  setDate: (date) => set({ selectedDate: date }),
  setPlayback: (playback) => set({ playback }),
  setSpeed: (speed) => set({ playbackSpeed: speed }),
  setPanel: (panel) => set({ activePanel: panel }),
  togglePanel: (panel) => set((state) => ({ activePanel: state.activePanel === panel ? null : panel })),
  setExpandedChart: (id) => set({ expandedChartVariableId: id }),
  setComparison: (comparison) => set({ comparison }),
  setNotice: (notice) => set({ notice }),
  setAssistantSessionId: (id) => set({ assistantSessionId: id }),
  ensureDate: (date) => {
    if (!get().selectedDate) set({ selectedDate: date });
  },
  applyAssistant: (actions, catalog) => {
    const current = get();
    const reduced = reduceAssistantActions(actions, current, catalog);
    const moved = reduced.session.selectedZoneId != null && reduced.session.selectedZoneId !== current.selectedZoneId;
    set({
      ...reduced.session,
      selectionNonce: moved ? current.selectionNonce + 1 : current.selectionNonce,
    });
    return reduced.results;
  },
}));
