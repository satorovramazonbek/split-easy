// Guruh sahifasi: xarajat formasida bo'lish usuliga qarab qiymat maydonlarini
// ko'rsatadi. Forma JavaScript'siz ham ishlaydi (server hammasini tekshiradi).
(() => {
  "use strict";
  const form = document.getElementById("groupExpenseForm");
  if (!form) return;
  const split = document.getElementById("ge-split");
  const hint = document.getElementById("ge-hint");
  const HINTS = {
    equal: "Summa belgilangan a'zolarga teng bo'linadi.",
    exact: "Har bir a'zo uchun summani kiriting — yig'indisi umumiy summaga teng bo'lishi kerak.",
    percentage: "Har bir a'zo uchun foizni kiriting — yig'indisi 100 bo'lishi kerak.",
    shares: "Har bir a'zo uchun ulush sonini kiriting (masalan, 2 va 1).",
  };
  const PLACEHOLDERS = { exact: "so'm", percentage: "%", shares: "ulush" };

  function update() {
    const type = split.value;
    for (const row of form.querySelectorAll(".share-row")) {
      const box = row.querySelector("input[type=checkbox]");
      const value = row.querySelector("input[type=number]");
      value.hidden = type === "equal";
      value.disabled = !box.checked;
      value.placeholder = PLACEHOLDERS[type] || "";
      value.step = type === "exact" ? "1" : "any";
    }
    hint.textContent = HINTS[type] || "";
  }

  split.addEventListener("change", update);
  form.addEventListener("change", (event) => {
    if (event.target.matches("input[type=checkbox]")) update();
  });
  document.getElementById("ge-toggle-all").addEventListener("click", () => {
    const boxes = [...form.querySelectorAll(".share-row input[type=checkbox]")];
    const check = boxes.some((b) => !b.checked);
    for (const b of boxes) b.checked = check;
    update();
  });
  update();
})();
