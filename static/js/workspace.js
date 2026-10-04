// Progressive enhancement only: the server validates previews and records stock.
(() => {
  const form = document.getElementById("adjustment-form");
  const data = document.getElementById("stock-choices");
  if (!form || !data) return;
  const quantities = new Map(JSON.parse(data.textContent).map(item => [String(item.id), item.stock_on_hand]));
  const product = form.elements.product;
  const change = form.elements.quantity_change;
  const estimate = document.getElementById("stock-estimate");
  const balanceLine = document.getElementById("estimated-balance-line");
  const current = document.getElementById("current-stock");
  const expected = document.getElementById("estimated-stock");
  const preview = document.getElementById("confirmed-preview");
  function update() {
    const stock = quantities.get(product.value);
    estimate.hidden = stock === undefined;
    current.textContent = stock === undefined ? "—" : stock;
    const delta = Number(change.value);
    const valid = change.value.trim() !== "" && Number.isSafeInteger(delta) && delta !== 0 && stock !== undefined;
    balanceLine.hidden = !valid;
    if (valid) expected.textContent = stock + delta;
  }
  form.addEventListener("input", () => {
    if (preview) {
      preview.hidden = true;
      preview.querySelector("button").disabled = true;
    }
    update();
  });
  update();
})();
