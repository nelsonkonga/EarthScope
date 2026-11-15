export type Basemap = "google" | "ion";

/** Google Photorealistic 3D Tiles when a key is set. Otherwise Cesium ion. */
export function selectBasemap(googleKey: string | undefined): Basemap {
  return googleKey?.trim() ? "google" : "ion";
}

export const HOME_CAMERA = {
  longitude: 11.52,
  latitude: 3.86,
  height: 1_400_000,
};

export const LABEL_HEIGHT_METERS = 2_500_000;
export const FLY_HEIGHT_METERS = 90_000;
export const FLY_PITCH_DEGREES = -90;
export const FLY_SECONDS = 0.8;
