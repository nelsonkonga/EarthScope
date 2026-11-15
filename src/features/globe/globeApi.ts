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

import type { GlobeField } from "../../domain/fieldView";

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
  setField: (field: GlobeField | null) => void;
  resize: () => void;
  reload: () => void;
};

let current: GlobeController | null = null;
let pendingMarkers: MarkerSpec[] = [];
let pendingField: GlobeField | null = null;

export function registerGlobe(controller: GlobeController | null) {
  current = controller;
  if (controller) {
    controller.setMarkers(pendingMarkers);
    controller.setField(pendingField);
  }
}

export function showMarkers(markers: MarkerSpec[]) {
  pendingMarkers = markers;
  current?.setMarkers(markers);
}

export function showField(field: GlobeField | null) {
  pendingField = field;
  current?.setField(field);
}

export function globe() {
  return current;
}
