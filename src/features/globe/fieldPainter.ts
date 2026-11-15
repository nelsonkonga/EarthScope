import {
  Cartesian3,
  Color,
  ColorMaterialProperty,
  ConstantProperty,
  PointPrimitiveCollection,
  Rectangle,
  type PointPrimitive,
  type Viewer,
} from "cesium";
import type { FieldLayer, Footprint, GlobeField } from "../../domain/fieldView";

type Swatch = {
  apply: (alpha: number) => void;
  base: number;
  pulse: boolean;
};

type Mote = {
  point: PointPrimitive;
  age: number;
  life: number;
  lon: number;
  lat: number;
  height: number;
  climb: number;
};

type Cloud = {
  points: PointPrimitiveCollection;
  motes: Mote[];
  color: string;
  motion: "rise" | "drift" | "fall";
  footprint: Footprint;
  base: number;
};

type Cohort = {
  entities: ReturnType<Viewer["entities"]["add"]>[];
  items: Swatch[];
  clouds: Cloud[];
};

function qualityScale() {
  const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
  return memory && memory <= 4 ? 0.45 : 1;
}

function swatch(color: string, alpha: number, pulse: boolean): { material: ColorMaterialProperty; item: Swatch } {
  const property = new ConstantProperty(Color.fromCssColorString(color).withAlpha(alpha));
  const material = new ColorMaterialProperty(property);
  return {
    material,
    item: {
      base: alpha,
      pulse,
      apply: (next) => property.setValue(Color.fromCssColorString(color).withAlpha(Math.max(0, Math.min(1, next)))),
    },
  };
}

function ring(footprint: Footprint, height: number) {
  const { west, south, east, north } = footprint;
  return Cartesian3.fromDegreesArrayHeights([west, south, height, east, south, height, east, north, height, west, north, height, west, south, height]);
}

function signature(field: GlobeField | null) {
  if (!field) return "";
  const { west, south, east, north } = field.footprint;
  const motion = field.animate === false ? "reduced" : "full";
  const layers = field.layers
    .map((layer) => [layer.variableId, layer.channel, layer.color, layer.alpha.toFixed(3), layer.altitude, layer.emit ? 1 : 0, layer.motion, layer.outline].join(":"))
    .join("|");
  return `${field.zoneId}|${motion}|${west},${south},${east},${north}|${layers}`;
}

/**
 * Draws the measured cell and fades between successive states.
 * The fade changes opacity only. It never invents a value between two dates.
 */
export function createFieldPainter(viewer: Viewer) {
  let current: Cohort | null = null;
  let previous: Cohort | null = null;
  let raf = 0;
  let pumping = false;
  let started = 0;
  let duration = 0;
  let seen = "\u0000";
  let allowMotion = true;
  const quality = qualityScale();

  let lastTick = 0;

  const drop = (cohort: Cohort | null) => {
    if (!cohort) return;
    for (const entity of cohort.entities) viewer.entities.remove(entity);
    for (const cloud of cohort.clouds) viewer.scene.primitives.remove(cloud.points);
  };

  const stepClouds = (cohort: Cohort | null, opacity: number, dt: number) => {
    if (!cohort) return;
    for (const cloud of cohort.clouds) {
      cloud.points.show = opacity > 0.04;
      for (const mote of cloud.motes) stepMote(mote, cloud, opacity, dt);
    }
  };

  const apply = (cohort: Cohort | null, opacity: number, wave: number) => {
    if (!cohort) return;
    for (const item of cohort.items) item.apply(item.base * opacity * (item.pulse ? wave : 1));
  };

  const stop = () => {
    if (pumping) cancelAnimationFrame(raf);
    pumping = false;
  };

  const frame = (now: number) => {
    const progress = duration <= 0 ? 1 : Math.min(1, (now - started) / duration);
    const wave = allowMotion ? 0.72 + 0.28 * Math.sin(now / 520) : 1;
    const dt = lastTick ? Math.min(0.05, (now - lastTick) / 1000) : 0.016;
    lastTick = now;
    apply(previous, 1 - progress, 1);
    apply(current, progress, progress >= 1 ? wave : 1);
    stepClouds(previous, 1 - progress, dt);
    stepClouds(current, progress, dt);
    const alive = Boolean(current && (current.clouds.length > 0 || current.items.some((item) => item.pulse)));
    viewer.scene.requestRender();
    if (progress >= 1 && previous) {
      drop(previous);
      previous = null;
    }
    if (progress < 1 || (alive && allowMotion)) {
      raf = requestAnimationFrame(frame);
      return;
    }
    pumping = false;
  };

  const start = () => {
    if (pumping) cancelAnimationFrame(raf);
    pumping = true;
    started = performance.now();
    raf = requestAnimationFrame(frame);
  };

  const build = (field: GlobeField): Cohort => {
    const cohort: Cohort = { entities: [], items: [], clouds: [] };
    const { footprint } = field;
    for (const layer of field.layers) addLayer(viewer, cohort, field, layer, footprint, allowMotion, quality);
    return cohort;
  };

  return {
    show(field: GlobeField | null) {
      const next = signature(field);
      if (next === seen) return;
      seen = next;
      if (field?.transitionMs != null) duration = field.transitionMs;
      else if (!duration) duration = 480;
      allowMotion = field ? field.animate !== false : allowMotion;
      if (field) duration = field.transitionMs ?? duration;
      drop(previous);
      previous = current;
      current = field ? build(field) : null;
      if (duration <= 0) {
        drop(previous);
        previous = null;
        apply(current, 1, 1);
        viewer.scene.requestRender();
        if (current && allowMotion && (current.clouds.length > 0 || current.items.some((item) => item.pulse))) start();
        else stop();
        return;
      }
      start();
    },
    destroy() {
      stop();
      drop(previous);
      drop(current);
      previous = null;
      current = null;
    },
  };
}

function spawn(mote: Mote, cloud: Cloud) {
  const { west, south, east, north } = cloud.footprint;
  mote.lon = west + Math.random() * (east - west);
  mote.lat = south + Math.random() * (north - south);
  mote.age = Math.random() * mote.life;
  if (cloud.motion === "fall") mote.height = cloud.base + 1600 + Math.random() * 1400;
  else if (cloud.motion === "drift") mote.height = cloud.base + 200 + Math.random() * 500;
  else mote.height = cloud.base + 500 + Math.random() * 400;
  mote.climb = cloud.motion === "fall" ? -(700 + Math.random() * 500) : cloud.motion === "drift" ? 40 + Math.random() * 70 : 500 + Math.random() * 500;
}

function moteColor(color: string, alpha: number) {
  const tint = Color.lerp(Color.fromCssColorString(color), Color.WHITE, 0.62, new Color());
  return tint.withAlpha(alpha);
}

function stepMote(mote: Mote, cloud: Cloud, opacity: number, dt: number) {
  mote.age += dt;
  mote.height += mote.climb * dt;
  if (mote.age >= mote.life || (cloud.motion === "fall" && mote.height < cloud.base)) spawn(mote, cloud);
  const grown = mote.age / mote.life;
  mote.point.position = Cartesian3.fromDegrees(mote.lon, mote.lat, mote.height);
  mote.point.pixelSize = cloud.motion === "fall" ? 5 : cloud.motion === "drift" ? 10 + grown * 8 : 9 + grown * 16;
  mote.point.color = moteColor(cloud.color, (cloud.motion === "drift" ? 0.45 : 0.9) * (1 - grown * 0.85) * opacity);
}

function addLayer(
  viewer: Viewer,
  cohort: Cohort,
  field: GlobeField,
  layer: FieldLayer,
  footprint: Footprint,
  allowMotion: boolean,
  quality: number,
) {
  const pulse = allowMotion && layer.motion === "pulse";
  if (layer.channel !== "halo") {
    const fill = swatch(layer.color, layer.alpha, false);
    cohort.items.push(fill.item);
    cohort.entities.push(
      viewer.entities.add({
        name: field.zoneId,
        rectangle: {
          coordinates: Rectangle.fromDegrees(footprint.west, footprint.south, footprint.east, footprint.north),
          height: layer.altitude,
          material: fill.material,
          fill: true,
          outline: false,
        },
      }),
    );
  }
  if (layer.outline !== "none") {
    const boundary = swatch(layer.color, layer.channel === "halo" ? layer.alpha : Math.min(0.95, layer.alpha + 0.28), pulse);
    cohort.items.push(boundary.item);
    const width = layer.channel === "halo" ? 2 + (layer.t ?? 0) * 3 : 2.5;
    cohort.entities.push(
      viewer.entities.add({
        name: field.zoneId,
        polyline: {
          positions: ring(footprint, layer.channel === "veil" ? 2440 : layer.altitude + 50),
          width,
          material: boundary.material,
        },
      }),
    );
    if (layer.outline === "double" && layer.channel !== "halo") {
      const inner = swatch(layer.color, layer.alpha * 0.55, false);
      cohort.items.push(inner.item);
      cohort.entities.push(
        viewer.entities.add({
          name: field.zoneId,
          polyline: {
            positions: ring(footprint, layer.altitude + 80),
            width: 6,
            material: inner.material,
          },
        }),
      );
    }
  }
  if (!layer.emit || !allowMotion || layer.t == null) return;
  const motion = layer.motion === "fall" ? "fall" : layer.motion === "drift" ? "drift" : "rise";
  const count = Math.round((motion === "rise" ? 14 + layer.t * 22 : motion === "fall" ? 16 + layer.t * 18 : 8 + layer.t * 10) * quality);
  const points = viewer.scene.primitives.add(new PointPrimitiveCollection());
  const cloud: Cloud = { points, motes: [], color: layer.color, motion, footprint, base: layer.altitude };
  for (let index = 0; index < count; index += 1) {
    const life = motion === "fall" ? 1.1 + Math.random() * 0.8 : motion === "drift" ? 3.2 + Math.random() : 2.2 + Math.random() * 1.4;
    const mote: Mote = {
      point: points.add({
        pixelSize: 6,
        color: Color.fromCssColorString(layer.color).withAlpha(0.45),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      }),
      age: 0,
      life,
      lon: footprint.west,
      lat: footprint.south,
      height: layer.altitude,
      climb: 0,
    };
    spawn(mote, cloud);
    cloud.motes.push(mote);
  }
  cohort.clouds.push(cloud);
}
