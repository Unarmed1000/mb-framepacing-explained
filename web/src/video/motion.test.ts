import { describe, expect, it } from "vitest";

import { onVideosPaused, setVideosPaused, videosPaused } from "./motion";

describe("the videos' pause switch", () => {
  it("plays by default without a stored choice or a reduced motion preference, and tells its listeners each change once", () => {
    expect(videosPaused()).toBe(false);
    const heard: boolean[] = [];
    onVideosPaused((paused) => heard.push(paused));
    setVideosPaused(true);
    setVideosPaused(true);
    expect(videosPaused()).toBe(true);
    setVideosPaused(false);
    expect(heard).toEqual([true, false]);
  });
});
