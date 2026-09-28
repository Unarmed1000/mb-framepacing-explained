// Self-guided slides: next / previous, a progress bar, a deep link per slide (#/id, and #/id/more for a view inside a slide),
// keyboard and swipe. After a jump (a link, not Next or Previous) the back button returns where the visitor came from, like the
// browser's Back.

import { resumeVideosIn } from "./video/pixel-video";

export interface Slide {
  id: string;
  title: string;
  render(): HTMLElement;
  /** Show the view at `path`, the part of the address after the slide's id ("" for the slide itself), on every visit. */
  route?(path: string): void;
}

/** The history entry's own state: the slide a jump came from, or null after Next / Previous. */
interface EntryState {
  from: string | null;
}

export function startSlides(
  root: HTMLElement,
  slides: readonly Slide[],
  links: readonly { href: string; label: string }[] = [],
  /** Who made the page, after its name in the top bar (hidden on narrow screens). */
  credit = "",
  /** Controls at the end of the top bar, after the slide counter. */
  tools: readonly HTMLElement[] = [],
): void {
  root.innerHTML = `
    <header class="topbar">
      <a class="brand" href="#/${slides[0]?.id ?? ""}">Frame pacing, explained</a>
      ${credit ? `<span class="credit">${credit}</span>` : ""}
      <div class="progress" role="progressbar" aria-valuemin="1"><span></span></div>
      <nav class="topbar-links" aria-label="Sections"></nav>
      <span class="counter"></span>
    </header>
    <main class="slides"></main>
    <nav class="bottombar" aria-label="Slides">
      <button type="button" class="button ghost" data-go="-1">← Previous</button>
      <span class="slide-title"></span>
      <button type="button" class="button" data-go="1">Next →</button>
    </nav>`;
  const main = root.querySelector<HTMLElement>(".slides")!;
  const bar = root.querySelector<HTMLElement>(".progress span")!;
  const progress = root.querySelector<HTMLElement>(".progress")!;
  const counter = root.querySelector<HTMLElement>(".counter")!;
  const title = root.querySelector<HTMLElement>(".slide-title")!;
  const previous = root.querySelector<HTMLButtonElement>('[data-go="-1"]')!;
  const next = root.querySelector<HTMLButtonElement>('[data-go="1"]')!;
  root.querySelector(".topbar")!.append(...tools);
  for (const link of links)
    root
      .querySelector(".topbar-links")!
      .append(Object.assign(document.createElement("a"), { href: link.href, textContent: link.label }));
  // Each slide is rendered once, when first shown, and kept (hidden) so its state survives going back and forth
  const rendered = new Map<string, HTMLElement>();
  let current = -1;
  // Set by Next / Previous, so the next address change is known to be a step, not a jump
  let stepping = false;

  const address = (): { index: number; path: string } => {
    const [id = "", ...rest] = location.hash.replace(/^#\/?/, "").split("/");
    const index = slides.findIndex((slide) => slide.id === id);
    return { index: index < 0 ? 0 : index, path: index < 0 ? "" : rest.join("/") };
  };

  /** Where the back button goes: after a jump, the slide it came from (with the browser's Back); else the slide before. */
  const updateBack = (index: number): void => {
    const from = (history.state as EntryState | null)?.from ?? null;
    const origin = from === null ? undefined : slides.find((slide) => slide.id === from);
    const jumped = origin !== undefined && origin !== slides[index - 1];
    previous.textContent = jumped ? `← Back to ${origin.title}` : "← Previous";
    previous.dataset.back = jumped ? "history" : "";
    previous.disabled = !jumped && index === 0;
  };

  const show = (index: number, path: string): void => {
    const slide = slides[index];
    if (!slide) return;
    const changed = index !== current;
    // Remember on the entry where it came from: a new entry after a jump from another slide; entries the browser goes back or
    // forward to keep what they had
    if (stepping) history.replaceState({ from: null } satisfies EntryState, "");
    else if (history.state === null)
      history.replaceState({ from: changed ? (slides[current]?.id ?? null) : null } satisfies EntryState, "");
    stepping = false;
    if (changed) {
      current = index;
      for (const [id, element] of rendered) {
        element.hidden = id !== slide.id;
        if (element.hidden) element.querySelectorAll("video").forEach((video) => video.pause());
      }
      let element = rendered.get(slide.id);
      if (!element) {
        element = document.createElement("section");
        element.className = "slide";
        element.dataset.slide = slide.id;
        element.append(slide.render());
        rendered.set(slide.id, element);
        main.append(element);
      } else {
        resumeVideosIn(element);
      }
      bar.style.width = `${((index + 1) / slides.length) * 100}%`;
      progress.setAttribute("aria-valuemax", String(slides.length));
      progress.setAttribute("aria-valuenow", String(index + 1));
      counter.textContent = `${index + 1} / ${slides.length}`;
      title.textContent = slide.title;
      document.title = `${slide.title} · Frame pacing, explained`;
      next.disabled = index === slides.length - 1;
    }
    slide.route?.(path);
    updateBack(index);
    main.scrollTop = 0;
  };

  const go = (step: number): void => {
    const target = slides[Math.min(slides.length - 1, Math.max(0, current + step))];
    if (!target || target === slides[current]) return;
    stepping = true;
    location.hash = `#/${target.id}`;
  };

  previous.addEventListener("click", () => (previous.dataset.back === "history" ? history.back() : go(-1)));
  next.addEventListener("click", () => go(1));
  window.addEventListener("hashchange", () => {
    const { index, path } = address();
    show(index, path);
  });
  document.addEventListener("keydown", (event) => {
    if (event.target instanceof HTMLInputElement || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === "ArrowRight" || event.key === "PageDown") go(1);
    if (event.key === "ArrowLeft" || event.key === "PageUp") go(-1);
  });
  let touchX: number | null = null;
  main.addEventListener("touchstart", (event) => (touchX = event.touches[0]?.clientX ?? null), { passive: true });
  main.addEventListener("touchend", (event) => {
    const endX = event.changedTouches[0]?.clientX;
    if (touchX !== null && endX !== undefined && Math.abs(endX - touchX) > 80) go(endX < touchX ? 1 : -1);
    touchX = null;
  });
  const { index, path } = address();
  history.replaceState({ from: null }, "");
  show(index, path);
}
