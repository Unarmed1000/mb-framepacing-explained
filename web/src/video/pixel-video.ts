// A looping video shown at 1:1 device pixels, with playback health from requestVideoFrameCallback.

import { cssSizeForDevicePixels, devicePixelBox, isOneToOne, snapOffset, type Size } from "../checks/scaling";
import { watchDevicePixelRatio } from "../checks/viewing";
import { onVideosPaused, setVideosPaused, videosPaused } from "./motion";

export interface PlaybackHealth {
  /** Video frames the browser presented. */
  presented: number;
  /** Video frames skipped between two presented ones (gaps in presentedFrames). */
  dropped: number;
  /** Video frames that reached the display half a frame or more later than the frame rate says. */
  late: number;
  /** Video frames that reached the display half a frame or more earlier than the frame rate says. */
  early: number;
}

export type FrameStep = "on-time" | "late" | "early" | "dropped";

/** Classify the step from one presented video frame to the next: the gap in presentedFrames and the change in
 * expectedDisplayTime (ms), against the video's frame period (ms). */
export function classifyStep(presentedGap: number, displayDeltaMs: number, periodMs: number): FrameStep {
  if (presentedGap > 1) return "dropped";
  if (displayDeltaMs >= periodMs * 1.5) return "late";
  if (displayDeltaMs <= periodMs * 0.5) return "early";
  return "on-time";
}

/** Every video made on the page, for the switch that pauses and plays them all; dropped once taken off the page. */
const players = new Set<PixelVideo>();

onVideosPaused((paused) => {
  for (const player of players) {
    if (!player.element.isConnected) players.delete(player);
    else if (paused) player.video.pause();
    else player.resume();
  }
});

/** Play the videos inside `root` again (a slide shown again) that were playing, unless the reader paused the videos. */
export function resumeVideosIn(root: HTMLElement): void {
  for (const player of players) if (root.contains(player.element)) player.resume();
}

/** Browsers without requestVideoFrameCallback (older ones) cannot report playback health. */
function hasFrameCallback(video: HTMLVideoElement): boolean {
  return "requestVideoFrameCallback" in video;
}

export class PixelVideo {
  readonly element: HTMLDivElement;
  readonly video: HTMLVideoElement;
  /** A line saying whether the video is shown 1:1, with its size and position in device pixels; the caller places it, out of
   * the way (below the answers), so it does not draw the eye. */
  readonly readout: HTMLParagraphElement;
  readonly health: PlaybackHealth = { presented: 0, dropped: 0, late: 0, early: 0 };
  /** Called with the video's media time for every presented frame (to move chart playheads), and after a seek. */
  onFrame: ((mediaTime: number) => void) | null = null;
  /** More callbacks like onFrame (the playback controls). */
  private readonly frameListeners: ((mediaTime: number) => void)[] = [];
  private lastPresented: number | null = null;
  private lastExpected: number | null = null;
  private lastMediaTime: number | null = null;
  /** Whether the page wants it playing (it was played and not paused since); it plays only while the videos are not paused. */
  private wanted = false;
  /** Over the video while the reader has paused the videos: a button to play them again. */
  private readonly pausedOverlay: HTMLButtonElement;
  /** Frames still to skip after a (re)start: while the decoder settles, the timing is irregular and says nothing. */
  private settling = 0;

  /** Holds the video; when only some rows are shown, it clips the rest. */
  private readonly frame: HTMLDivElement;

  /** `rows`: show only these video rows, from (inclusive) to (exclusive), still at 1:1 device pixels, e.g. one box of a pair. */
  constructor(
    src: string,
    private readonly size: Size,
    private readonly fps: number,
    private readonly options: { rows?: { from: number; to: number }; label?: string } = {},
  ) {
    this.element = document.createElement("div");
    this.element.className = "pixel-video";
    this.frame = document.createElement("div");
    this.frame.className = options.rows === undefined ? "pixel-frame" : "pixel-frame cropped";
    this.video = document.createElement("video");
    Object.assign(this.video, {
      src,
      muted: true,
      loop: true,
      playsInline: true,
      preload: "auto",
      disablePictureInPicture: true,
    });
    this.video.setAttribute("aria-label", options.label ?? "Two boxes moving; compare the top and the bottom");
    this.readout = document.createElement("p");
    this.readout.className = "pixel-readout";
    this.pausedOverlay = document.createElement("button");
    this.pausedOverlay.type = "button";
    this.pausedOverlay.className = "video-paused";
    this.pausedOverlay.innerHTML = `<span aria-hidden="true">▶</span> Play videos`;
    this.pausedOverlay.title = "Play every video on the page (P)";
    this.pausedOverlay.hidden = true;
    this.pausedOverlay.addEventListener("click", () => setVideosPaused(false));
    this.frame.append(this.video, this.pausedOverlay);
    this.element.append(this.frame);
    players.add(this);
    for (const event of ["play", "pause"]) this.video.addEventListener(event, () => this.updateOverlay());
    onVideosPaused(() => this.updateOverlay());
    const layout = (): void => this.layout();
    window.addEventListener("resize", layout);
    // Any scrolling ancestor (the slides scroll inside their own area) moves the video: capture every scroll on the page
    document.addEventListener("scroll", layout, { passive: true, capture: true });
    new ResizeObserver(layout).observe(document.documentElement);
    watchDevicePixelRatio(layout);
    requestAnimationFrame(layout);
    // A pause, seek, stall or hidden tab is a gap in playback, not a late frame: start the frame tracking over after one
    for (const event of ["play", "pause", "seeking", "waiting"]) this.video.addEventListener(event, () => this.restartTracking());
    // A seek while paused presents no frame to the frame callback: tell the listeners where the video is now
    this.video.addEventListener("seeked", () => this.frameShown(this.video.currentTime));
    document.addEventListener("visibilitychange", () => this.restartTracking());
    this.watchFrames();
  }

  /** Forget the previous frame, so the next step is not compared with one from before a gap; the counts stay. */
  private restartTracking(): void {
    this.lastPresented = null;
    this.lastExpected = null;
    this.lastMediaTime = null;
    this.settling = Math.round(this.fps / 2);
  }

  /** Size the video to exactly its pixel size in device pixels and move it onto whole device pixels. */
  layout(): void {
    const ratio = window.devicePixelRatio || 1;
    const css = cssSizeForDevicePixels(this.size, ratio);
    Object.assign(this.video.style, { width: `${css.width}px`, height: `${css.height}px`, transform: "none" });
    const rect = this.video.getBoundingClientRect();
    const dx = snapOffset(rect.left, ratio);
    const dy = snapOffset(rect.top, ratio);
    // Shown rows: the video moves up by the rows above them (whole device pixels, so it stays on the grid), and the frame ends
    // exactly below the last one: the rows' height plus the shift that snapped the video
    const rows = this.options.rows;
    this.video.style.transform = `translate(${dx}px, ${dy - (rows ? rows.from / ratio : 0)}px)`;
    if (rows) this.frame.style.height = `${(rows.to - rows.from) / ratio + dy}px`;
    this.report();
  }

  /** Measure where the video really is, in device pixels, and say whether it is 1:1. */
  report(): boolean {
    const ratio = window.devicePixelRatio || 1;
    const box = devicePixelBox(this.video.getBoundingClientRect(), ratio);
    const exact = isOneToOne(box, this.size);
    const number = (value: number): string =>
      Math.abs(value - Math.round(value)) < 0.005 ? String(Math.round(value)) : value.toFixed(2);
    const scale = `scale ${Math.round(ratio * 100)} %`;
    this.readout.dataset.status = exact ? "ok" : "fail";
    this.readout.textContent = exact
      ? `1:1: ${this.size.width} x ${this.size.height} device pixels (${scale})`
      : `Not 1:1: ${number(box.width)} x ${number(box.height)} device pixels at ${number(box.left)}, ${number(box.top)} (${scale})`;
    return exact;
  }

  /** Also call `listener` with the media time of every presented frame, and after a seek. */
  addFrameListener(listener: (mediaTime: number) => void): void {
    this.frameListeners.push(listener);
  }

  private frameShown(mediaTime: number): void {
    this.onFrame?.(mediaTime);
    for (const listener of this.frameListeners) listener(mediaTime);
  }

  /** Play it, as the page does on its own: only while the reader has not paused the videos. */
  play(): void {
    this.wanted = true;
    this.resume();
    this.updateOverlay();
  }

  /** Play it because the reader asked for this video (its own play button), even while the other videos are paused. */
  playNow(): void {
    this.wanted = true;
    void this.video.play();
  }

  pause(): void {
    this.wanted = false;
    this.video.pause();
    this.updateOverlay();
  }

  /** Play it again if the page wants it playing, the videos are not paused and it is on the slide shown. */
  resume(): void {
    if (this.wanted && !videosPaused() && this.element.closest("[hidden]") === null) void this.video.play();
  }

  private updateOverlay(): void {
    this.pausedOverlay.hidden = !(this.wanted && videosPaused() && this.video.paused);
  }

  resetHealth(): void {
    Object.assign(this.health, { presented: 0, dropped: 0, late: 0, early: 0 });
    this.lastPresented = null;
    this.lastExpected = null;
  }

  private watchFrames(): void {
    if (!hasFrameCallback(this.video)) return;
    const video = this.video;
    const period = 1000 / this.fps;
    const step: VideoFrameRequestCallback = (_now, metadata) => {
      // The loop wraps the media time back to the start: a restart, not a late frame
      if (this.lastMediaTime !== null && metadata.mediaTime < this.lastMediaTime) this.restartTracking();
      this.lastMediaTime = metadata.mediaTime;
      if (this.settling > 0) {
        this.settling -= 1;
      } else if (this.lastPresented !== null && this.lastExpected !== null) {
        const gap = metadata.presentedFrames - this.lastPresented;
        const step = classifyStep(gap, metadata.expectedDisplayTime - this.lastExpected, period);
        if (step === "dropped") this.health.dropped += gap - 1;
        else if (step === "late") this.health.late += 1;
        else if (step === "early") this.health.early += 1;
      }
      this.health.presented += 1;
      this.lastPresented = metadata.presentedFrames;
      this.lastExpected = metadata.expectedDisplayTime;
      this.frameShown(metadata.mediaTime);
      video.requestVideoFrameCallback(step);
    };
    this.restartTracking();
    video.requestVideoFrameCallback(step);
  }
}
