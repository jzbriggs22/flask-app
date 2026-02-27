/**
 * PDF Viewer engine built on PDF.js.
 *
 * Renders PDF pages to a canvas with support for:
 * - Multi-page navigation
 * - Zoom and pan (smooth at 60fps target)
 * - Scale calibration overlay
 * - Measurement annotation rendering
 *
 * Performance-critical: construction drawings can be 100+ MB / 500+ sheets.
 */

export interface PdfViewerOptions {
  container: HTMLDivElement;
  /** Initial zoom level (1 = 100%) */
  initialZoom?: number;
  /** Callback when a page is rendered */
  onPageRendered?: (pageIndex: number) => void;
  /** Callback when zoom level changes */
  onZoomChange?: (zoom: number) => void;
}

interface ViewerState {
  currentPage: number;
  totalPages: number;
  zoom: number;
  panX: number;
  panY: number;
}

export class PdfViewer {
  private container: HTMLDivElement;
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private state: ViewerState;
  private options: PdfViewerOptions;

  constructor(options: PdfViewerOptions) {
    this.options = options;
    this.container = options.container;

    this.canvas = document.createElement("canvas");
    this.canvas.className = "pdf-canvas";
    this.canvas.style.width = "100%";
    this.canvas.style.height = "100%";
    this.container.appendChild(this.canvas);

    const ctx = this.canvas.getContext("2d");
    if (!ctx) throw new Error("Could not get 2D canvas context");
    this.ctx = ctx;

    this.state = {
      currentPage: 0,
      totalPages: 0,
      zoom: options.initialZoom ?? 1,
      panX: 0,
      panY: 0,
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
    // this.renderPage(0);
  }

  /** Navigate to a specific page (0-indexed) */
  goToPage(pageIndex: number): void {
    if (pageIndex < 0 || pageIndex >= this.state.totalPages) return;
    this.state.currentPage = pageIndex;
    this.render();
  }

  /** Set zoom level */
  setZoom(zoom: number): void {
    this.state.zoom = Math.max(0.1, Math.min(10, zoom));
    this.options.onZoomChange?.(this.state.zoom);
    this.render();
  }

  /** Get current state */
  getState(): Readonly<ViewerState> {
    return { ...this.state };
  }

  /** Clean up resources */
  destroy(): void {
    this.canvas.remove();
  }

  private render(): void {
    // TODO: Implement rendering pipeline
    // 1. Clear canvas
    // 2. Apply zoom and pan transforms
    // 3. Render PDF page
    // 4. Render measurement overlays
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.options.onPageRendered?.(this.state.currentPage);
  }

  private setupEventListeners(): void {
    // Wheel zoom
    this.canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      this.setZoom(this.state.zoom + delta);
    });

    // Pan with middle mouse / shift+left
    let isPanning = false;
    let lastX = 0;
    let lastY = 0;

    this.canvas.addEventListener("mousedown", (e) => {
      if (e.button === 1 || (e.button === 0 && e.shiftKey)) {
        isPanning = true;
        lastX = e.clientX;
        lastY = e.clientY;
      }
    });

    this.canvas.addEventListener("mousemove", (e) => {
      if (!isPanning) return;
      this.state.panX += e.clientX - lastX;
      this.state.panY += e.clientY - lastY;
      lastX = e.clientX;
      lastY = e.clientY;
      this.render();
    });

    this.canvas.addEventListener("mouseup", () => {
      isPanning = false;
    });
  }
}
