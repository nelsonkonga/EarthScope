import {
  Cartesian3,
  Color,
  ColorMaterialProperty,
  ConstantProperty,
  PointPrimitiveCollection,
  PolygonHierarchy,
  Rectangle,
  type PointPrimitive,
  type Viewer,
} from "cesium";
import type { FieldLayer, Footprint, GlobeField } from "../../domain/fieldView";

/**
 * One colored surface (fill, outline, inner glow). It glides from the color it shows now
 * toward its target color, so a change of month or of variable scrolls through the
 * intermediate hues instead of jumping. Only the display moves; the target is always
 * the measured value of the selected date.
 */
type Swatch = {
  key: string;
  property: ConstantProperty;
  from: Color;
  to: Color;
  shown: Color;
  fromAlpha: number;
  toAlpha: number;
  shownAlpha: number;
  pulse: boolean;
  width?: { property: ConstantProperty; from: number; to: number };
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
  key: string;
  points: PointPrimitiveCollection;
  motes: Mote[];
  from: Color;
  to: Color;
  shown: Color;
  motion: "rise" | "drift" | "fall";
  footprint: Footprint;
  base: number;
};

type Cohort = {
  structure: string;
  entities: ReturnType<Viewer["entities"]["add"]>[];
  items: Swatch[];
  clouds: Cloud[];
};

const scratch = new Color();

function qualityScale() {
  const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
  return memory && memory <= 4 ? 0.45 : 1;
}

/** Smooth start and end, so the hue accelerates out of the old color and settles on the new one. */
function ease(progress: number) {
  return progress < 0.5 ? 4 * progress ** 3 : 1 - (-2 * progress + 2) ** 3 / 2;
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function swatch(key: string, color: string, alpha: number, pulse: boolean): { material: ColorMaterialProperty; item: Swatch } {
  const target = Color.fromCssColorString(color);
  const property = new ConstantProperty(target.withAlpha(0));
  return {
    material: new ColorMaterialProperty(property),
    item: {
      key,
      property,
      from: target.clone(),
      to: target.clone(),
      shown: target.clone(),
      fromAlpha: 0,
      toAlpha: alpha,
      shownAlpha: 0,
      pulse,
    },
  };
}

function paint(item: Swatch, t: number, wave: number) {
  Color.lerp(item.from, item.to, t, item.shown);
  item.shownAlpha = lerp(item.fromAlpha, item.toAlpha, t);
  const alpha = Math.max(0, Math.min(1, item.shownAlpha * (item.pulse && t >= 1 ? wave : 1)));
  item.property.setValue(Color.clone(item.shown, scratch).withAlpha(alpha));
  if (item.width) item.width.property.setValue(lerp(item.width.from, item.width.to, t));
}

function outline(footprint: Footprint, height: number) {
  if (footprint.ring && footprint.ring.length >= 4) {
    const flat: number[] = [];
    for (const [lon, lat] of footprint.ring) flat.push(lon, lat, height);
    const [lon0, lat0] = footprint.ring[0];
    const [lonN, latN] = footprint.ring[footprint.ring.length - 1];
    if (lon0 !== lonN || lat0 !== latN) flat.push(lon0, lat0, height);
    return Cartesian3.fromDegreesArrayHeights(flat);
  }
  const { west, south, east, north } = footprint;
  return Cartesian3.fromDegreesArrayHeights([west, south, height, east, south, height, east, north, height, west, north, height, west, south, height]);
}

function inside(ring: [number, number][], lon: number, lat: number) {
  let hit = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi || 1e-12) + xi) hit = !hit;
  }
  return hit;
}

function geometryKey(field: GlobeField) {
  const { west, south, east, north, ring } = field.footprint;
  return `${field.zoneId}|${west},${south},${east},${north}|${ring?.length ?? 0}|${field.animate === false ? "reduced" : "full"}`;
}

/** What has to be rebuilt. Colors, opacities and halo widths are not part of it: they glide in place. */
function structureOf(field: GlobeField | null) {
  if (!field) return "";
  const layers = field.layers
    .map((layer) => [layer.variableId, layer.channel, layer.altitude, layer.emit ? 1 : 0, layer.motion, layer.outline].join(":"))
    .join("|");
  return `${geometryKey(field)}|${layers}`;
}

function signature(field: GlobeField | null) {
  if (!field) return "";
  return `${structureOf(field)}|${field.layers.map((layer) => `${layer.color}:${layer.alpha.toFixed(3)}:${layer.t ?? ""}`).join("|")}`;
}

/** Halo width grows with the reading. */
function haloWidth(layer: FieldLayer) {
  return layer.channel === "halo" ? 2 + (layer.t ?? 0) * 3 : 2.5;
}

/**
 * Draws the measured zone and glides between successive states.
 * The glide interpolates the displayed color only. It never invents a value between two dates.
 */
export function createFieldPainter(viewer: Viewer) {
  let current: Cohort | null = null;
  let leaving: Cohort | null = null;
  let raf = 0;
  let pumping = false;
  let started = 0;
  let duration = 480;
  let seen = "\u0000";
  let allowMotion = true;
  let lastTick = 0;
  const quality = qualityScale();

  const drop = (cohort: Cohort | null) => {
    if (!cohort) return;
    for (const entity of cohort.entities) viewer.entities.remove(entity);
    for (const cloud of cohort.clouds) viewer.scene.primitives.remove(cloud.points);
  };

  const stop = () => {
    if (pumping) cancelAnimationFrame(raf);
    pumping = false;
  };

  const frame = (now: number) => {
    const progress = duration <= 0 ? 1 : Math.min(1, (now - started) / duration);
    const t = ease(progress);
    const wave = allowMotion ? 0.72 + 0.28 * Math.sin(now / 520) : 1;
    const dt = lastTick ? Math.min(0.05, (now - lastTick) / 1000) : 0.016;
    lastTick = now;
    if (current) {
      for (const item of current.items) paint(item, t, wave);
      for (const cloud of current.clouds) {
        Color.lerp(cloud.from, cloud.to, t, cloud.shown);
        cloud.points.show = true;
        for (const mote of cloud.motes) stepMote(mote, cloud, 1, dt);
      }
    }
    if (leaving) {
      for (const item of leaving.items) {
        item.toAlpha = 0;
        paint(item, t, 1);
      }
      for (const cloud of leaving.clouds) {
        cloud.points.show = 1 - t > 0.04;
        for (const mote of cloud.motes) stepMote(mote, cloud, 1 - t, dt);
      }
    }
    viewer.scene.requestRender();
    if (progress >= 1 && leaving) {
      drop(leaving);
      leaving = null;
    }
    const alive = Boolean(current && (current.clouds.length > 0 || current.items.some((item) => item.pulse)));
    if (progress < 1 || (alive && allowMotion)) {
      raf = requestAnimationFrame(frame);
      return;
    }
    pumping = false;
  };

  const start = () => {
    started = performance.now();
    if (pumping) return;
    pumping = true;
    lastTick = 0;
    raf = requestAnimationFrame(frame);
  };

  /** Every swatch starts from what is on screen now and heads for its new target. */
  const rebase = (cohort: Cohort) => {
    for (const item of cohort.items) {
      Color.clone(item.shown, item.from);
      item.fromAlpha = item.shownAlpha;
    }
    for (const cloud of cohort.clouds) Color.clone(cloud.shown, cloud.from);
  };

  const retarget = (cohort: Cohort, field: GlobeField) => {
    rebase(cohort);
    const byKey = new Map(cohort.items.map((item) => [item.key, item]));
    field.layers.forEach((layer, index) => {
      for (const target of targetsFor(layer, index)) {
        const item = byKey.get(target.key);
        if (!item) continue;
        Color.fromCssColorString(target.color, item.to);
        item.toAlpha = target.alpha;
        if (item.width && target.width != null) item.width = { ...item.width, from: item.width.property.getValue() as number, to: target.width };
      }
      const cloud = cohort.clouds.find((entry) => entry.key === `${index}:cloud`);
      if (cloud) Color.fromCssColorString(layer.color, cloud.to);
    });
  };

  return {
    show(field: GlobeField | null) {
      const next = signature(field);
      if (next === seen) return;
      seen = next;
      if (field) {
        duration = field.transitionMs ?? duration;
        allowMotion = field.animate !== false;
      }
      const structure = structureOf(field);
      if (field && current && current.structure === structure) {
        retarget(current, field);
      } else {
        drop(leaving);
        const old = current;
        if (old) rebase(old);
        current = field ? build(viewer, field, structure, allowMotion, quality) : null;
        // Surfaces that exist on both sides inherit the old on-screen color and glide from it.
        const inherited = new Set<string>();
        if (old && current) {
          const previous = new Map(old.items.map((item) => [item.key, item]));
          for (const item of current.items) {
            const match = previous.get(item.key);
            if (!match) continue;
            Color.clone(match.shown, item.from);
            item.fromAlpha = match.shownAlpha;
            inherited.add(item.key);
          }
          const previousClouds = new Map(old.clouds.map((cloud) => [cloud.key, cloud]));
          for (const cloud of current.clouds) {
            const match = previousClouds.get(cloud.key);
            if (match) Color.clone(match.shown, cloud.from);
          }
        }
        if (old) {
          // Matched surfaces disappear at once (the new one takes their place and color); the rest fade out.
          const keep: Cohort = { structure: old.structure, entities: [], items: [], clouds: old.clouds };
          old.entities.forEach((entity, index) => {
            const item = old.items[index];
            if (item && inherited.has(item.key)) viewer.entities.remove(entity);
            else {
              keep.entities.push(entity);
              if (item) {
                Color.clone(item.from, item.to);
                keep.items.push(item);
              }
            }
          });
          leaving = keep;
        } else leaving = null;
      }
      if (duration <= 0) {
        drop(leaving);
        leaving = null;
        if (current) {
          for (const item of current.items) paint(item, 1, 1);
          for (const cloud of current.clouds) Color.clone(cloud.to, cloud.shown);
        }
        viewer.scene.requestRender();
        if (current && allowMotion && (current.clouds.length > 0 || current.items.some((item) => item.pulse))) start();
        else stop();
        return;
      }
      start();
    },
    destroy() {
      stop();
      drop(leaving);
      drop(current);
      leaving = null;
      current = null;
    },
  };
}

type Target = { key: string; role: "fill" | "boundary" | "inner"; color: string; alpha: number; width?: number };

function targetsFor(layer: FieldLayer, index: number): Target[] {
  const targets: Target[] = [];
  if (layer.channel !== "halo") targets.push({ key: `${index}:fill`, role: "fill", color: layer.color, alpha: layer.alpha });
  if (layer.outline !== "none") {
    targets.push({
      key: `${index}:boundary`,
      role: "boundary",
      color: layer.color,
      alpha: layer.channel === "halo" ? layer.alpha : Math.min(0.95, layer.alpha + 0.28),
      width: haloWidth(layer),
    });
    if (layer.outline === "double" && layer.channel !== "halo") {
      targets.push({ key: `${index}:inner`, role: "inner", color: layer.color, alpha: layer.alpha * 0.55 });
    }
  }
  return targets;
}

function build(viewer: Viewer, field: GlobeField, structure: string, allowMotion: boolean, quality: number): Cohort {
  const cohort: Cohort = { structure, entities: [], items: [], clouds: [] };
  field.layers.forEach((layer, index) => addLayer(viewer, cohort, field, layer, index, allowMotion, quality));
  return cohort;
}

function spawn(mote: Mote, cloud: Cloud) {
  const { west, south, east, north, ring } = cloud.footprint;
  for (let attempt = 0; attempt < 12; attempt += 1) {
    mote.lon = west + Math.random() * (east - west);
    mote.lat = south + Math.random() * (north - south);
    if (!ring || inside(ring, mote.lon, mote.lat)) break;
  }
  mote.age = Math.random() * mote.life;
  if (cloud.motion === "fall") mote.height = cloud.base + 1600 + Math.random() * 1400;
  else if (cloud.motion === "drift") mote.height = cloud.base + 200 + Math.random() * 500;
  else mote.height = cloud.base + 500 + Math.random() * 400;
  mote.climb = cloud.motion === "fall" ? -(700 + Math.random() * 500) : cloud.motion === "drift" ? 40 + Math.random() * 70 : 500 + Math.random() * 500;
}

const moteTint = new Color();

function stepMote(mote: Mote, cloud: Cloud, opacity: number, dt: number) {
  mote.age += dt;
  mote.height += mote.climb * dt;
  if (mote.age >= mote.life || (cloud.motion === "fall" && mote.height < cloud.base)) spawn(mote, cloud);
  const grown = mote.age / mote.life;
  mote.point.position = Cartesian3.fromDegrees(mote.lon, mote.lat, mote.height);
  mote.point.pixelSize = cloud.motion === "fall" ? 5 : cloud.motion === "drift" ? 10 + grown * 8 : 9 + grown * 16;
  Color.lerp(cloud.shown, Color.WHITE, 0.62, moteTint);
  mote.point.color = moteTint.withAlpha((cloud.motion === "drift" ? 0.45 : 0.9) * (1 - grown * 0.85) * opacity);
}

function addLayer(viewer: Viewer, cohort: Cohort, field: GlobeField, layer: FieldLayer, index: number, allowMotion: boolean, quality: number) {
  const pulse = allowMotion && layer.motion === "pulse";
  const { footprint } = field;
  for (const target of targetsFor(layer, index)) {
    const made = swatch(target.key, target.color, target.alpha, target.role === "boundary" && pulse);
    cohort.items.push(made.item);
    if (target.role === "fill") {
      const shape = footprint.ring
        ? {
            polygon: {
              hierarchy: new PolygonHierarchy(Cartesian3.fromDegreesArray(footprint.ring.flat())),
              height: layer.altitude,
              material: made.material,
              fill: true,
              outline: false,
            },
          }
        : {
            rectangle: {
              coordinates: Rectangle.fromDegrees(footprint.west, footprint.south, footprint.east, footprint.north),
              height: layer.altitude,
              material: made.material,
              fill: true,
              outline: false,
            },
          };
      cohort.entities.push(viewer.entities.add({ name: field.zoneId, ...shape }));
      continue;
    }
    const width = new ConstantProperty(target.role === "inner" ? 6 : (target.width ?? 2.5));
    if (target.role === "boundary") made.item.width = { property: width, from: target.width ?? 2.5, to: target.width ?? 2.5 };
    cohort.entities.push(
      viewer.entities.add({
        name: field.zoneId,
        polyline: {
          positions: outline(footprint, target.role === "inner" ? layer.altitude + 80 : layer.channel === "veil" ? 2440 : layer.altitude + 50),
          width,
          material: made.material,
        },
      }),
    );
  }
  if (!layer.emit || !allowMotion || layer.t == null) return;
  const motion = layer.motion === "fall" ? "fall" : layer.motion === "drift" ? "drift" : "rise";
  const count = Math.round((motion === "rise" ? 14 + layer.t * 22 : motion === "fall" ? 16 + layer.t * 18 : 8 + layer.t * 10) * quality);
  const points = viewer.scene.primitives.add(new PointPrimitiveCollection());
  const color = Color.fromCssColorString(layer.color);
  const cloud: Cloud = {
    key: `${index}:cloud`,
    points,
    motes: [],
    from: color.clone(),
    to: color.clone(),
    shown: color.clone(),
    motion,
    footprint,
    base: layer.altitude,
  };
  for (let count_ = 0; count_ < count; count_ += 1) {
    const life = motion === "fall" ? 1.1 + Math.random() * 0.8 : motion === "drift" ? 3.2 + Math.random() : 2.2 + Math.random() * 1.4;
    const mote: Mote = {
      point: points.add({ pixelSize: 6, color: color.withAlpha(0), disableDepthTestDistance: Number.POSITIVE_INFINITY }),
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
