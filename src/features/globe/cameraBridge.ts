export type CameraSample = {
  latitude: number | null;
  longitude: number | null;
  height: number | null;
  scale: string;
};

const empty: CameraSample = { latitude: null, longitude: null, height: null, scale: "—" };
let sample = empty;
const listeners = new Set<() => void>();

export function publishCamera(next: CameraSample) {
  sample = next;
  listeners.forEach((listener) => listener());
}

export function subscribeCamera(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getCameraSample() {
  return sample;
}
