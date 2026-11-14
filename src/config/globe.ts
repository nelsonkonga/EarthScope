export type Basemap = "google" | "ion";

/** Google Photorealistic 3D Tiles when a key is set. Otherwise Cesium ion. */
export function selectBasemap(googleKey: string | undefined): Basemap {
  return googleKey?.trim() ? "google" : "ion";
}

export const HOME_CAMERA = {
  longitude: 0,
  latitude: 0,
  height: 16_000_000,
};

export const LABEL_HEIGHT_METERS = 2_500_000;
export const DISC_HEIGHT_METERS = 400_000;
export const SYMBOL_RADIUS_METERS = 40_000;
export const FLY_HEIGHT_METERS = 80_000;
export const FLY_PITCH_DEGREES = -45;
export const FLY_SECONDS = 0.8;
