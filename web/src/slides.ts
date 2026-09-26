// Self-guided slides: next / previous, a progress bar, a deep link per slide (#/id), keyboard and swipe.

export interface Slide {
  id: string;
  title: string;
  render(): HTMLElement;
}

export function startSlides(root: HTMLElement, slides: readonly Slide[]): void {
  root.innerHTML = `
    <header class="topbar">
      <a class="brand" href="#/${slides[0]?.id ?? ""}">Frame pacing, explained</a>
      <div class="progress" role="progressbar" aria-valuemin="1"><span></span></div>
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
  // Each slide is rendered once, when first shown, and kept (hidden) so its state survives going back and forth
  const rendered = new Map<string, HTMLElement>();
  let current = -1;

  const indexFromHash = (): number => {
    const id = location.hash.replace(/^#\/?/, "");
    const index = slides.findIndex((slide) => slide.id === id);
    return index < 0 ? 0 : index;
  };

  const show = (index: number): void => {
    const slide = slides[index];
    if (!slide || index === current) return;
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
      element.querySelectorAll("video").forEach((video) => void video.play());
    }
    bar.style.width = `${((index + 1) / slides.length) * 100}%`;
    progress.setAttribute("aria-valuemax", String(slides.length));
    progress.setAttribute("aria-valuenow", String(index + 1));
    counter.textContent = `${index + 1} / ${slides.length}`;
    title.textContent = slide.title;
    document.title = `${slide.title} · Frame pacing, explained`;
    previous.disabled = index === 0;
    next.disabled = index === slides.length - 1;
    main.scrollTop = 0;
  };

  const go = (step: number): void => {
    const target = slides[Math.min(slides.length - 1, Math.max(0, current + step))];
    if (target) location.hash = `#/${target.id}`;
  };

  previous.addEventListener("click", () => go(-1));
  next.addEventListener("click", () => go(1));
  window.addEventListener("hashchange", () => show(indexFromHash()));
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
  show(indexFromHash());
}
