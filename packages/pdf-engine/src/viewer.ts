/**
 * PDF Viewer engine built on PDF.js (Spec §3).
 *
 * Rendering model:
 *   - PDF.js renders pages into a canvas (or layered canvases).
 *   - Overlay is a separate <canvas> aligned to the PDF viewport.
 *   - Overlay uses the same transformation as PDF viewport.
 *   - Hit-testing and drawing happen in WORLD, projected to CSS_PX each frame.
 *
 * Performance-critical: construction drawings can be 100+ MB / 500+ sheets.
 * Performance budget (§13): pan/zoom must maintain near-60fps.
 */

import type { TransformState, WorldPoint, ScreenPoint } from "@openbuild/types";
import { screenToWorld, worldToScreen } from "./transforms";

export interface PdfViewerOptions {
  container: HTMLDivElement;
  initialZoom?: number;
  onPageRendered?: (pageIndex: number) => void;
  onZoomChange?: (zoom: number) => void;
  /** Called when the TransformState changes (zoom, pan, page switch) */
  onTransformChange?: (transform: TransformState) => void;
  /** Called with pointer WORLD coordinates on move (for tools/snapping) */
  onPointerMoveWorld?: (world: WorldPoint, screen: ScreenPoint) => void;
  /** Called with pointer WORLD coordinates on click (for measurement placement) */
  onPointerClickWorld?: (world: WorldPoint, screen: ScreenPoint) => void;
}

interface ViewerState {
  currentPage: number;
  totalPages: number;
  transform: TransformState;
}

export class PdfViewer {
  private container: HTMLDivElement;
  private pdfCanvas: HTMLCanvasElement;
  private overlayCanvas: HTMLCanvasElement;
  private pdfCtx: CanvasRenderingContext2D;
  private overlayCtx: CanvasRenderingContext2D;
  private state: ViewerState;
  private options: PdfViewerOptions;
  private animFrameId: number | null = null;

  constructor(options: PdfViewerOptions) {
    this.options = options;
    this.container = options.container;
    this.container.style.position = "relative";
    this.container.style.overflow = "hidden";

    // PDF layer
    this.pdfCanvas = document.createElement("canvas");
    this.pdfCanvas.className = "pdf-canvas";
    this.pdfCanvas.style.position = "absolute";
    this.pdfCanvas.style.top = "0";
    this.pdfCanvas.style.left = "0";
    this.container.appendChild(this.pdfCanvas);

    // Overlay layer (measurement annotations)
    this.overlayCanvas = document.createElement("canvas");
    this.overlayCanvas.className = "measurement-overlay";
    this.overlayCanvas.style.position = "absolute";
    this.overlayCanvas.style.top = "0";
    this.overlayCanvas.style.left = "0";
    this.container.appendChild(this.overlayCanvas);

    const pdfCtx = this.pdfCanvas.getContext("2d");
    const overlayCtx = this.overlayCanvas.getContext("2d");
    if (!pdfCtx || !overlayCtx) throw new Error("Could not get 2D canvas context");
    this.pdfCtx = pdfCtx;
    this.overlayCtx = overlayCtx;

    this.state = {
      currentPage: 0,
      totalPages: 0,
      transform: {
        pageId: "",
        sheetRevisionId: "",
        pdfViewportScale: 1,
        pdfViewportRotation: 0,
        panX: 0,
        panY: 0,
        zoom: options.initialZoom ?? 1,
        devicePixelRatio: window.devicePixelRatio,
        pageWidthPt: 612, // Default US Letter width in PDF_PT
        pageHeightPt: 792,
      },
    };

    this.setupEventListeners();
  }

  /**
   * Load a PDF from a URL or ArrayBuffer.
   * Uses PDF.js to parse the document.
   */
  async loadDocument(_source: string | ArrayBuffer): Promise<void> {
    // TODO: Implement PDF.js document loading
    // const pdfjsLib = await import('pdfjs-dist');
    // const doc = await pdfjsLib.getDocument(source).promise;
    // this.state.totalPages = doc.numPages;
    //
    // For each page:
    //   const page = await doc.getPage(pageNum);
    //   const viewport = page.getViewport({ scale: 1 });
    //   Store pageWidthPt = viewport.width, pageHeightPt = viewport.height
    //   These are the WORLD dimensions we persist geometry against.
    //
    // this.renderPage(0);
  }

  /** Navigate to a specific page (0-indexed) */
  goToPage(pageIndex: number): void {
    if (pageIndex < 0 || pageIndex >= this.state.totalPages) return;
    this.state.currentPage = pageIndex;
    this.scheduleRender();
  }

  /** Set zoom level */
  setZoom(zoom: number): void {
    this.state.transform.zoom = Math.max(0.1, Math.min(10, zoom));
    this.options.onZoomChange?.(this.state.transform.zoom);
    this.emitTransformChange();
    this.scheduleRender();
  }

  /** Get current transform state for external coordinate conversions */
  getTransform(): Readonly<TransformState> {
    return { ...this.state.transform };
  }

  /** Get the overlay canvas context for external rendering (measurements, etc.) */
  getOverlayContext(): CanvasRenderingContext2D {
    return this.overlayCtx;
  }

  /** Get overlay canvas dimensions */
  getOverlaySize(): { width: number; height: number } {
    return {
      width: this.overlayCanvas.width,
      height: this.overlayCanvas.height,
    };
  }

  /** Convert screen point to WORLD using current transform */
  screenToWorld(screen: ScreenPoint): WorldPoint {
    return screenToWorld(screen, this.state.transform);
  }

  /** Convert WORLD point to screen using current transform */
  worldToScreen(world: WorldPoint): ScreenPoint {
    return worldToScreen(world, this.state.transform);
  }

  /** Clean up resources */
  destroy(): void {
    if (this.animFrameId !== null) {
      cancelAnimationFrame(this.animFrameId);
    }
    this.pdfCanvas.remove();
    this.overlayCanvas.remove();
  }

  // ============================================================
  // Rendering
  // ============================================================

  private scheduleRender(): void {
    if (this.animFrameId !== null) return;
    this.animFrameId = requestAnimationFrame(() => {
      this.animFrameId = null;
      this.render();
    });
  }

  private render(): void {
    const { width, height } = this.container.getBoundingClientRect();
    const dpr = this.state.transform.devicePixelRatio;

    // Size canvases
    for (const canvas of [this.pdfCanvas, this.overlayCanvas]) {
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
    }

    // Clear
    this.pdfCtx.clearRect(0, 0, this.pdfCanvas.width, this.pdfCanvas.height);
    this.overlayCtx.clearRect(0, 0, this.overlayCanvas.width, this.overlayCanvas.height);

    // TODO: Implement PDF page rendering pipeline
    // 1. Get current page from PDF.js document
    // 2. Compute viewport at pdfViewportScale
    // 3. Apply zoom and pan transforms
    // 4. Render to pdfCanvas
    //
    // The overlay canvas is cleared here; external code
    // (TakeoffPage) draws measurement geometry using
    // worldToScreen() for each point.

    this.options.onPageRendered?.(this.state.currentPage);
  }

  // ============================================================
  // Event handling
  // ============================================================

  private emitTransformChange(): void {
    this.options.onTransformChange?.(this.state.transform);
  }

  private getCanvasPoint(e: MouseEvent): ScreenPoint {
    const rect = this.overlayCanvas.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  private setupEventListeners(): void {
    // Wheel zoom (centered on cursor)
    this.overlayCanvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      const cursor = this.getCanvasPoint(e);

      // Zoom centered on cursor position
      const oldZoom = this.state.transform.zoom;
      const newZoom = Math.max(0.1, Math.min(10, oldZoom + delta));
      const zoomRatio = newZoom / oldZoom;

      this.state.transform.panX = cursor.x - (cursor.x - this.state.transform.panX) * zoomRatio;
      this.state.transform.panY = cursor.y - (cursor.y - this.state.transform.panY) * zoomRatio;
      this.state.transform.zoom = newZoom;

      this.options.onZoomChange?.(newZoom);
      this.emitTransformChange();
      this.scheduleRender();
    });

    // Pan with middle mouse / shift+left
    let isPanning = false;
    let lastX = 0;
    let lastY = 0;

    this.overlayCanvas.addEventListener("mousedown", (e) => {
      if (e.button === 1 || (e.button === 0 && e.shiftKey)) {
        isPanning = true;
        lastX = e.clientX;
        lastY = e.clientY;
        e.preventDefault();
      }
    });

    this.overlayCanvas.addEventListener("mousemove", (e) => {
      const screen = this.getCanvasPoint(e);

      if (isPanning) {
        this.state.transform.panX += e.clientX - lastX;
        this.state.transform.panY += e.clientY - lastY;
        lastX = e.clientX;
        lastY = e.clientY;
        this.emitTransformChange();
        this.scheduleRender();
        return;
      }

      // Emit WORLD coordinates for tools/snapping
      const world = screenToWorld(screen, this.state.transform);
      this.options.onPointerMoveWorld?.(world, screen);
    });

    this.overlayCanvas.addEventListener("mouseup", (e) => {
      if (isPanning) {
        isPanning = false;
        return;
      }

      // Non-pan click: emit for measurement tools
      if (e.button === 0 && !e.shiftKey) {
        const screen = this.getCanvasPoint(e);
        const world = screenToWorld(screen, this.state.transform);
        this.options.onPointerClickWorld?.(world, screen);
      }
    });

    // Prevent context menu on overlay
    this.overlayCanvas.addEventListener("contextmenu", (e) => e.preventDefault());
  }
}
