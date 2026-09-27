/** A refresh strip of the first 1/6 s of `fps` on a `hz` display, one cell per refresh, the shade changing with each new frame
 * (after the average chart's strips), and how many refreshes each frame is held. A frame is shown at the first refresh at or after
 * the moment it is due, as with plain vsync; the rows share one time scale, so the strips line up (a refresh rate that 1/6 s does
 * not divide, like 500 Hz, ends in a part of a cell). A slide asks for one with `::strip HZ FPS`. */
export function refreshStrip(hz: number, fps: number): string {
  const refreshes = hz / 6;
  const flips: number[] = [];
  // Integers throughout: k x hz / fps is exact whenever it is whole
  for (let frame = 0; Math.ceil((frame * hz) / fps) < refreshes; frame++) flips.push(Math.ceil((frame * hz) / fps));
  const cells: string[] = [];
  let shade = 0;
  for (let refresh = 0; refresh < refreshes; refresh++) {
    if (refresh > 0 && flips.includes(refresh)) shade ^= 1;
    const part = refreshes - refresh < 1 ? ` style="flex: ${(refreshes - refresh).toFixed(3)}"` : "";
    cells.push(`<span${shade ? ' class="b"' : ""}${part}></span>`);
  }
  const holds = flips.slice(1).map((flip, index) => flip - (flips[index] ?? 0));
  const even = holds.every((hold) => hold === holds[0]);
  const shown = even
    ? `every frame ${holds[0]} refreshes, ${((1000 * (holds[0] ?? 0)) / hz).toFixed(1).replace(/\.0$/, "")} ms`
    : `${holds.slice(0, 5).join(", ")} … refreshes: uneven`;
  return `<div class="strip-row">
      <div class="strip-label"><strong>${fps} fps on ${hz} Hz</strong><span>${shown}</span></div>
      <div class="refresh-strip">${cells.join("")}</div>
    </div>`;
}
