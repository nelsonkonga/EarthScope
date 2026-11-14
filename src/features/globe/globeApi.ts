export type MarkerSpec = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  fill: string;
  rings: string[];
  dashed: boolean;
  dimmed: boolean;
  emphasized: boolean;
  selected: boolean;
};

export type GlobeStatus =
  | { phase: "loading" }
  | { phase: "ready" }
  | { phase: "error"; message: string };

export type GlobeController = {
  destroy: () => void;
  zoomIn: () => void;
  zoomOut: () => void;
  home: () => void;
  flyTo: (longitude: number, latitude: number) => void;
  pan: (direction: "left" | "right" | "up" | "down") => void;
  orbit: (direction: "left" | "right") => void;
  setMarkers: (markers: MarkerSpec[]) => void;
  resize: () => void;
  reload: () => void;
};

let current: GlobeController | null = null;
let pendingMarkers: MarkerSpec[] = [];

export function registerGlobe(controller: GlobeController | null) {
  current = controller;
  if (controller) controller.setMarkers(pendingMarkers);
}

export function showMarkers(markers: MarkerSpec[]) {
  pendingMarkers = markers;
  current?.setMarkers(markers);
}

export function globe() {
  return current;
}
