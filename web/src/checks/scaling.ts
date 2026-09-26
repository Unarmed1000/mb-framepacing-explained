// Showing a video at 1:1 device pixels at any browser zoom or display scaling (devicePixelRatio).

export interface Size {
  width: number;
  height: number;
}

/** The CSS size that makes a video of `video` pixels exactly that many device pixels at the given ratio. */
export function cssSizeForDevicePixels(video: Size, devicePixelRatio: number): Size {
  return { width: video.width / devicePixelRatio, height: video.height / devicePixelRatio };
}

/** The CSS offset that moves a CSS position onto a whole device pixel, so the video's pixels line up with the display's. */
export function snapOffset(cssPosition: number, devicePixelRatio: number): number {
  const device = cssPosition * devicePixelRatio;
  return (Math.round(device) - device) / devicePixelRatio;
}

/** Whether a video of `video` pixels fits a viewport of `viewport` CSS pixels at 1:1 device pixels. */
export function fitsAtDevicePixels(video: Size, viewport: Size, devicePixelRatio: number): boolean {
  return viewport.width * devicePixelRatio >= video.width && viewport.height * devicePixelRatio >= video.height;
}

export interface DevicePixelBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** An element's box (from getBoundingClientRect, in CSS pixels) in device pixels. */
export function devicePixelBox(rect: DevicePixelBox, devicePixelRatio: number): DevicePixelBox {
  return {
    left: rect.left * devicePixelRatio,
    top: rect.top * devicePixelRatio,
    width: rect.width * devicePixelRatio,
    height: rect.height * devicePixelRatio,
  };
}

/** Whether a device-pixel box shows a video of `video` pixels 1:1: exactly its size, on whole device pixels. */
export function isOneToOne(box: DevicePixelBox, video: Size, tolerance = 0.02): boolean {
  const whole = (value: number): boolean => Math.abs(value - Math.round(value)) <= tolerance;
  return (
    Math.abs(box.width - video.width) <= tolerance &&
    Math.abs(box.height - video.height) <= tolerance &&
    whole(box.left) &&
    whole(box.top)
  );
}
