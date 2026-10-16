(() => {
  const root = document.querySelector<HTMLElement>(".landing-page");
  if (!root) return;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (!reduced.matches) root.classList.add("lp-motion-ready");
  const story = root.querySelector<HTMLElement>("[data-stock-story]");
  const count = root.querySelector<HTMLElement>("[data-story-count]");
  const description = root.querySelector<HTMLElement>("[data-story-description]");
  const replay = root.querySelector<HTMLButtonElement>("[data-story-replay]");
  const status = root.querySelector<HTMLElement>("[data-story-status]");
  const units = Array.from(root.querySelectorAll<HTMLElement>(".lp-unit"));
  const rows = Array.from(root.querySelectorAll<HTMLElement>("[data-story-step]"));
  const timers: number[] = [];
  let played = false;
  const frames = [
    { quantity: 12, text: "The shop opens with 12 units of Rice." },
    { quantity: 20, text: "A completed Purchase adds 8 units. The shelf now holds 20." },
    { quantity: 15, text: "A completed Sale removes 5 units. Both movements stay in the history." },
  ];
  const clear = () => { timers.splice(0).forEach(window.clearTimeout); };
  const show = (index: number, immediate = false) => {
    const frame = frames[index];
    if (count) count.textContent = String(frame.quantity);
    if (description) description.textContent = frame.text;
    story?.setAttribute("data-story-phase", String(index));
    units.forEach((unit, position) => {
      // CSS transitions retarget from the rendered position on interruption.
      unit.style.transitionDelay = immediate ? "0ms" : `${Math.max(0, position - (index === 1 ? 12 : 15)) * 45}ms`;
      unit.classList.toggle("lp-unit-empty", position >= frame.quantity);
      unit.classList.toggle("lp-unit-sold", index === 2 && position >= 15);
    });
    rows.forEach((row, position) => row.classList.toggle("lp-current", position === index));
  };
  const settle = () => { clear(); story?.classList.add("lp-instant"); show(2, true); };
  const play = () => {
    clear(); played = true;
    if (reduced.matches || document.hidden) { settle(); return; }
    story?.classList.remove("lp-instant");
    show(0);
    timers.push(window.setTimeout(() => show(1), 900));
    timers.push(window.setTimeout(() => show(2), 2300));
    timers.push(window.setTimeout(() => {
      if (status) status.textContent = "Example complete: 15 units remain. Purchase and Sale movements retained.";
    }, 3100));
  };
  if (replay) {
    replay.hidden = false;
    replay.addEventListener("click", (event) => {
      if (status) status.textContent = "";
      if (event.detail === 0 || reduced.matches) {
        played = true; settle();
        if (status) status.textContent = "Example complete: opening stock 12, Purchase plus 8, Sale minus 5, closing stock 15. Original movements retained.";
      } else play();
    });
  }
  reduced.addEventListener("change", () => {
    if (reduced.matches) { root.classList.remove("lp-motion-ready"); settle(); }
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden) settle(); });
  root.querySelectorAll<HTMLElement>(".lp-button, .lp-replay").forEach((button) => {
    button.addEventListener("pointerdown", () => { if (!reduced.matches) button.classList.add("lp-pointer-pressed"); });
    ["pointerup", "pointercancel", "pointerleave", "blur", "keydown"].forEach((name) => {
      button.addEventListener(name, () => button.classList.remove("lp-pointer-pressed"));
    });
  });
  if ("IntersectionObserver" in window) {
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        if (!reduced.matches) entry.target.classList.add("lp-revealed");
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.15 });
    root.querySelectorAll("[data-reveal]").forEach((element) => revealObserver.observe(element));
    if (story) {
      const storyObserver = new IntersectionObserver((entries, observer) => {
        if (entries.some((entry) => entry.isIntersecting) && !played) { play(); observer.disconnect(); }
      }, { threshold: 0.35 });
      storyObserver.observe(story);
    }
  }
})();
