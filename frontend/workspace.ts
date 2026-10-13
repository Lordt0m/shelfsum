// Enhancements only. Django owns money, stock, validation and authorization.
(() => {
  const errorSummary = document.querySelector<HTMLElement>("#error-summary");
  errorSummary?.focus();
  document.querySelectorAll<HTMLElement>(".field-invalid").forEach((field) => {
    const input = field.querySelector<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>("input, select, textarea");
    const error = field.querySelector<HTMLElement>(".field-errors");
    if (input && error) {
      input.setAttribute("aria-invalid", "true");
      const ids = new Set((input.getAttribute("aria-describedby") ?? "").split(" ").filter(Boolean));
      ids.add(error.id);
      input.setAttribute("aria-describedby", [...ids].join(" "));
    }
  });

  const adjustment = document.querySelector<HTMLFormElement>("#adjustment-form");
  const preview = document.querySelector<HTMLElement>("#confirmed-preview");
  adjustment?.addEventListener("input", () => {
    if (preview) {
      preview.hidden = true;
      preview.querySelectorAll<HTMLButtonElement>("button").forEach((button) => { button.disabled = true; });
    }
    const hint = document.querySelector<HTMLElement>("#preview-hint");
    if (hint) hint.hidden = false;
    const current = document.querySelector<HTMLElement>("#stock-estimate");
    if (current) current.hidden = true;
  });

  document.querySelectorAll<HTMLFormElement>("[data-document-form]").forEach((form) => {
    const total = form.querySelector<HTMLInputElement>('[name="lines-TOTAL_FORMS"]');
    const maximum = form.querySelector<HTMLInputElement>('[name="lines-MAX_NUM_FORMS"]');
    const template = form.querySelector<HTMLTemplateElement>("[data-line-template]");
    const rows = form.querySelector<HTMLElement>("[data-line-rows]");
    const add = form.querySelector<HTMLButtonElement>('[name="add_line"]');
    const feedback = form.querySelector<HTMLElement>("[data-line-feedback]");
    if (!total || !template || !rows || !add) return;
    add.addEventListener("click", (event) => {
      event.preventDefault();
      const count = Number(total.value);
      const limit = Number(maximum?.value || 1000);
      if (!Number.isSafeInteger(count) || count < 0 || count >= limit) {
        if (feedback) feedback.textContent = "No more rows can be added to this document.";
        return;
      }
      const holder = document.createElement("template");
      holder.innerHTML = template.innerHTML.replaceAll("__prefix__", String(count));
      const fragment = holder.content;
      const legend = fragment.querySelector("legend");
      if (legend) legend.textContent = `Product line ${count + 1}`;
      const firstInput = fragment.querySelector<HTMLElement>("select, input:not([type=hidden])");
      rows.append(fragment);
      total.value = String(count + 1);
      if (feedback) feedback.textContent = `Product line ${count + 1} added. Nothing has been saved.`;
      firstInput?.focus();
    });
    form.addEventListener("input", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement) || !target.closest("[data-line-rows]")) return;
      form.querySelectorAll<HTMLElement>("[data-saved-total]").forEach((output) => { output.hidden = true; });
      const hint = form.querySelector<HTMLElement>("[data-total-hint]");
      if (hint) hint.textContent = "Totals will be recalculated when you save this draft.";
    });
  });

  const restore = () => document.querySelectorAll<HTMLFormElement>('form[aria-busy="true"]').forEach((form) => {
    form.removeAttribute("aria-busy");
    form.querySelectorAll<HTMLButtonElement>("[data-submitting]").forEach((button) => {
      button.textContent = button.dataset.originalLabel ?? "Submit";
      button.removeAttribute("aria-disabled");
      delete button.dataset.submitting;
    });
  });
  // Preserve name/value of submitter; disabling it would lose preview/add-line intent.
  document.querySelectorAll<HTMLFormElement>("form").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (form.getAttribute("aria-busy") === "true") { event.preventDefault(); return; }
      const button = (event as SubmitEvent).submitter;
      if (!(button instanceof HTMLButtonElement)) return;
      form.setAttribute("aria-busy", "true");
      button.dataset.originalLabel = button.textContent ?? "Submit";
      button.dataset.submitting = "true";
      button.setAttribute("aria-disabled", "true");
      button.textContent = form.method === "get" ? "Applying…" : "Working…";
    });
  });
  window.addEventListener("pageshow", restore);
})();
