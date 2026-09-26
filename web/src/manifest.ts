// The manifest.json the video tool writes next to each folder of clips (tools/frame_pacing_video/generate_videos.py).

export interface ModeFrames {
  /** The output refresh each frame first appears on. */
  refresh: number[];
  /** The animation error of each frame, PresentMon's MsAnimationError (positive: shown too soon). */
  animationErrorMs: number[];
  dtMs: number[];
  sampleMs: number[];
}

export interface ModeEntry {
  mode: string;
  rate: number;
  timer: "ideal" | "naive";
  noise: string | null;
  noiseWindowMs: number | null;
  label: string;
  frames: ModeFrames;
}

export interface VideoEntry {
  file: string;
  speed: string;
  scene: string;
  fps: number;
  frameCount: number;
  videoFrameCount: number;
  width: number;
  height: number;
  top: ModeEntry;
  bottom: ModeEntry;
}

export interface Manifest {
  generator: string;
  settings: { fps: number; web?: boolean; width: number; height: number };
  videos: VideoEntry[];
}

/** Load a folder's manifest and its raw text; the folder is relative to the page (e.g. "videos/box/fast"). */
export async function loadManifestText(folder: string): Promise<{ manifest: Manifest; text: string }> {
  const response = await fetch(`${folder}/manifest.json`);
  if (!response.ok) throw new Error(`${folder}/manifest.json: ${response.status} ${response.statusText}`);
  const text = await response.text();
  return { manifest: JSON.parse(text) as Manifest, text };
}

export async function loadManifest(folder: string): Promise<Manifest> {
  return (await loadManifestText(folder)).manifest;
}
