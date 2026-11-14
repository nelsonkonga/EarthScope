import {
  BillboardCollection,
  CameraEventType,
  Cartesian2,
  Cartesian3,
  Cartographic,
  Cesium3DTileset,
  ClassificationType,
  Color,
  Ellipsoid,
  HeightReference,
  KeyboardEventModifier,
  LabelCollection,
  LabelStyle,
  Math as CesiumMath,
  NearFarScalar,
  RequestScheduler,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  SkyAtmosphere,
  VerticalOrigin,
  Viewer,
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import { DISC_HEIGHT_METERS, FLY_HEIGHT_METERS, FLY_PITCH_DEGREES, FLY_SECONDS, HOME_CAMERA, LABEL_HEIGHT_METERS, SYMBOL_RADIUS_METERS } from "../../config/globe";
import { niceDistance } from "../../domain/format";
import { publishCamera } from "./cameraBridge";
import { registerGlobe, type GlobeController, type GlobeStatus, type MarkerSpec } from "./globeApi";

type Hooks = {
  onZone: (id: string) => void;
  onEmpty: () => void;
  onStatus: (status: GlobeStatus) => void;
};

const images = new Map<string, HTMLCanvasElement>();

function markerImage(spec: MarkerSpec): HTMLCanvasElement {
  const key = `${spec.fill}|${spec.rings.join()}|${spec.dashed}|${spec.selected}|${spec.dimmed}`;
  const cached = images.get(key);
  if (cached) return cached;
  const canvas = document.createElement("canvas");
  canvas.width = 64;
  canvas.height = 64;
  const context = canvas.getContext("2d");
  if (!context) return canvas;
  const alpha = spec.dimmed ? 0.4 : 1;
  context.clearRect(0, 0, 64, 64);
  context.globalAlpha = alpha;
  if (spec.selected) {
    context.beginPath();
    context.arc(32, 32, 22, 0, Math.PI * 2);
    context.strokeStyle = "#8eabc4";
    context.lineWidth = 3;
    context.stroke();
  }
  spec.rings.forEach((color, index) => {
    context.beginPath();
    context.arc(32, 32, 16 + index * 4, 0, Math.PI * 2);
    context.strokeStyle = color;
    context.lineWidth = 2;
    context.stroke();
  });
  context.beginPath();
  context.arc(32, 32, 9, 0, Math.PI * 2);
  context.fillStyle = spec.fill;
  context.fill();
  if (spec.dashed) {
    context.setLineDash([3, 2]);
    context.strokeStyle = "#f4efe6";
    context.lineWidth = 2;
    context.stroke();
  }
  images.set(key, canvas);
  return canvas;
}

function reducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function createGlobe(container: HTMLElement, credits: HTMLElement, hooks: Hooks): GlobeController {
  const canvas = document.createElement("canvas");
  const webgl = canvas.getContext("webgl2");
  if (!webgl) {
    hooks.onStatus({ phase: "error", message: "webgl" });
    const inert: GlobeController = {
      destroy: () => undefined,
      zoomIn: () => undefined,
      zoomOut: () => undefined,
      home: () => undefined,
      flyTo: () => undefined,
      pan: () => undefined,
      orbit: () => undefined,
      setMarkers: () => undefined,
      resize: () => undefined,
      reload: () => undefined,
    };
    registerGlobe(inert);
    return inert;
  }

  RequestScheduler.requestsByServer["tile.googleapis.com:443"] = 18;
  const viewer = new Viewer(container, {
    animation: false,
    timeline: false,
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    sceneModePicker: false,
    navigationHelpButton: false,
    fullscreenButton: false,
    infoBox: false,
    selectionIndicator: false,
    baseLayer: false,
    globe: false,
    requestRenderMode: true,
    creditContainer: credits,
    skyAtmosphere: new SkyAtmosphere(),
  });
  if (viewer.scene.skyAtmosphere) viewer.scene.skyAtmosphere.show = false;
  viewer.scene.backgroundColor = Color.BLACK;
  const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
  if (memory && memory <= 4) {
    viewer.resolutionScale = 0.75;
    viewer.scene.postProcessStages.fxaa.enabled = false;
  }
  const controller = viewer.scene.screenSpaceCameraController;
  controller.rotateEventTypes = CameraEventType.LEFT_DRAG;
  controller.tiltEventTypes = [
    CameraEventType.RIGHT_DRAG,
    CameraEventType.PINCH,
    { eventType: CameraEventType.LEFT_DRAG, modifier: KeyboardEventModifier.CTRL },
  ];
  controller.zoomEventTypes = [CameraEventType.WHEEL, CameraEventType.PINCH];
  controller.minimumZoomDistance = 80;
  controller.maximumZoomDistance = 40_000_000;

  const billboards = viewer.scene.primitives.add(new BillboardCollection());
  const labels = viewer.scene.primitives.add(new LabelCollection());
  let specs: MarkerSpec[] = [];
  let tileset: Cesium3DTileset | null = null;
  let pointer: Cartesian2 | null = null;
  let lastPublish = 0;
  let clickTimer = 0;
  let discVisible = false;

  const homeView = () => {
    viewer.camera.setView({
      destination: Cartesian3.fromDegrees(HOME_CAMERA.longitude, HOME_CAMERA.latitude, HOME_CAMERA.height),
      orientation: { heading: 0, pitch: CesiumMath.toRadians(-90), roll: 0 },
    });
  };

  const fly = (longitude: number, latitude: number) => {
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(longitude, latitude, FLY_HEIGHT_METERS),
      orientation: { heading: 0, pitch: CesiumMath.toRadians(FLY_PITCH_DEGREES), roll: 0 },
      duration: reducedMotion() ? 0 : FLY_SECONDS,
    });
  };

  const drawMarkers = () => {
    billboards.removeAll();
    labels.removeAll();
    viewer.entities.removeAll();
    const height = viewer.camera.positionCartographic?.height ?? Number.POSITIVE_INFINITY;
    discVisible = height < DISC_HEIGHT_METERS;
    for (const spec of specs) {
      const position = Cartesian3.fromDegrees(spec.longitude, spec.latitude);
      billboards.add({
        position,
        image: markerImage(spec),
        id: spec.id,
        verticalOrigin: VerticalOrigin.CENTER,
        scale: spec.emphasized ? 1.25 : 1,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        scaleByDistance: new NearFarScalar(2.0e5, 1.15, 1.8e7, 0.55),
      });
      labels.add({
        position,
        text: spec.name,
        font: "600 14px Segoe UI, sans-serif",
        fillColor: Color.WHITE,
        outlineColor: Color.BLACK,
        outlineWidth: 3,
        style: LabelStyle.FILL_AND_OUTLINE,
        verticalOrigin: VerticalOrigin.BOTTOM,
        pixelOffset: new Cartesian2(0, -18),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        show: spec.selected || height < LABEL_HEIGHT_METERS,
      });
      if (height < DISC_HEIGHT_METERS && spec.fill !== "#ffffff") {
        viewer.entities.add({
          position,
          ellipse: {
            semiMajorAxis: SYMBOL_RADIUS_METERS,
            semiMinorAxis: SYMBOL_RADIUS_METERS,
            material: Color.fromCssColorString(spec.fill).withAlpha(spec.dimmed ? 0.18 : 0.38),
            heightReference: HeightReference.CLAMP_TO_3D_TILE,
            classificationType: ClassificationType.CESIUM_3D_TILE,
          },
        });
      }
    }
    viewer.scene.requestRender();
  };

  const publish = (force = false) => {
    const now = performance.now();
    if (!force && now - lastPublish < 100) return;
    lastPublish = now;
    const canvasSize = viewer.canvas;
    const center = new Cartesian2(canvasSize.clientWidth / 2, canvasSize.clientHeight / 2);
    const target = viewer.camera.pickEllipsoid(pointer ?? center, Ellipsoid.WGS84);
    const carto = Cartographic.fromCartesian(viewer.camera.position);
    const point = target ? Cartographic.fromCartesian(target) : carto;
    let scale = "—";
    const left = viewer.camera.pickEllipsoid(new Cartesian2(center.x - 50, center.y), Ellipsoid.WGS84);
    const right = viewer.camera.pickEllipsoid(new Cartesian2(center.x + 50, center.y), Ellipsoid.WGS84);
    if (left && right) scale = niceDistance(Cartesian3.distance(left, right));
    publishCamera({
      latitude: CesiumMath.toDegrees(point.latitude),
      longitude: CesiumMath.toDegrees(point.longitude),
      height: carto.height,
      scale,
    });
    const height = carto.height;
    const nextDisc = height < DISC_HEIGHT_METERS;
    if (nextDisc !== discVisible) {
      discVisible = nextDisc;
      drawMarkers();
      return;
    }
    for (let index = 0; index < labels.length; index += 1) {
      const spec = specs[index];
      labels.get(index).show = Boolean(spec && (spec.selected || height < LABEL_HEIGHT_METERS));
    }
  };

  viewer.camera.percentageChanged = 0.01;
  viewer.camera.changed.addEventListener(() => publish());
  viewer.camera.moveEnd.addEventListener(() => publish(true));
  const moveHandler = new ScreenSpaceEventHandler(viewer.scene.canvas);
  moveHandler.setInputAction((movement: { endPosition: Cartesian2 }) => {
    pointer = movement.endPosition;
    publish();
  }, ScreenSpaceEventType.MOUSE_MOVE);
  moveHandler.setInputAction((click: { position: Cartesian2 }) => {
    window.clearTimeout(clickTimer);
    clickTimer = window.setTimeout(() => {
      const picked = viewer.scene.pick(click.position) as { id?: unknown } | undefined;
      if (picked && typeof picked.id === "string") hooks.onZone(picked.id);
      else hooks.onEmpty();
    }, 220);
  }, ScreenSpaceEventType.LEFT_CLICK);
  moveHandler.setInputAction(() => {
    window.clearTimeout(clickTimer);
    const height = viewer.camera.positionCartographic?.height ?? 1_000_000;
    viewer.camera.zoomIn(height * 0.35);
  }, ScreenSpaceEventType.LEFT_DOUBLE_CLICK);

  const loadTileset = () => {
    const key = import.meta.env.VITE_GOOGLE_MAPS_API_KEY?.trim();
    if (!key) {
      hooks.onStatus({ phase: "error", message: "key" });
      return;
    }
    hooks.onStatus({ phase: "loading" });
    const url = `https://tile.googleapis.com/v1/3dtiles/root.json?key=${encodeURIComponent(key)}`;
    void Cesium3DTileset.fromUrl(url, { showCreditsOnScreen: true })
      .then((next) => {
        if (tileset) viewer.scene.primitives.remove(tileset);
        tileset = next;
        viewer.scene.primitives.add(tileset);
        if (viewer.scene.skyAtmosphere) viewer.scene.skyAtmosphere.show = true;
        viewer.scene.requestRender();
        hooks.onStatus({ phase: "ready" });
      })
      .catch(() => hooks.onStatus({ phase: "error", message: "load" }));
  };

  homeView();
  publish(true);
  loadTileset();

  const api: GlobeController = {
    destroy: () => {
      window.clearTimeout(clickTimer);
      moveHandler.destroy();
      registerGlobe(null);
      viewer.destroy();
    },
    zoomIn: () => viewer.camera.zoomIn((viewer.camera.positionCartographic?.height ?? 1) * 0.35),
    zoomOut: () => viewer.camera.zoomOut((viewer.camera.positionCartographic?.height ?? 1) * 0.35),
    home: () => {
      if (reducedMotion()) homeView();
      else {
        viewer.camera.flyTo({
          destination: Cartesian3.fromDegrees(HOME_CAMERA.longitude, HOME_CAMERA.latitude, HOME_CAMERA.height),
          orientation: { heading: 0, pitch: CesiumMath.toRadians(-90), roll: 0 },
          duration: FLY_SECONDS,
        });
      }
    },
    flyTo: fly,
    pan: (direction) => {
      const distance = Math.max(1000, (viewer.camera.positionCartographic?.height ?? 1) * 0.08);
      if (direction === "left") viewer.camera.moveLeft(distance);
      if (direction === "right") viewer.camera.moveRight(distance);
      if (direction === "up") viewer.camera.moveUp(distance);
      if (direction === "down") viewer.camera.moveDown(distance);
      viewer.scene.requestRender();
    },
    orbit: (direction) => {
      viewer.camera.rotateLeft(direction === "left" ? 0.08 : -0.08);
      viewer.scene.requestRender();
    },
    setMarkers: (markers) => {
      specs = markers;
      drawMarkers();
    },
    resize: () => viewer.resize(),
    reload: loadTileset,
  };
  registerGlobe(api);
  return api;
}
