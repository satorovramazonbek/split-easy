// SplitEasy — barcha ma'lumotlar faqat shu sahifa xotirasida saqlanadi.
// Sahifa yangilansa, hammasi o'chadi (ro'yxatdan o'tish ham, baza ham yo'q).
(() => {
  "use strict";

  const state = {
    participants: [], // {id, name}
    expenses: [], // {id, description, amount, paid_by, split_type, participants, shares}
    nextParticipantId: 1,
    nextExpenseId: 1,
  };

  const SPLIT_LABELS = {
    equal: "teng",
    exact: "aniq summalar",
    percentage: "foiz bo'yicha",
    shares: "ulushlar bo'yicha",
  };
  const SPLIT_HINTS = {
    equal: "Summa belgilangan ishtirokchilarga teng bo'linadi.",
    exact: "Har bir ishtirokchi uchun summani kiriting — yig'indisi umumiy summaga teng bo'lishi kerak.",
    percentage: "Har bir ishtirokchi uchun foizni kiriting — yig'indisi 100 bo'lishi kerak.",
    shares: "Har bir ishtirokchi uchun ulush sonini kiriting (masalan, 2 va 1).",
  };
  const SERVER_ERRORS = [
    [/Exact amounts sum \((\d+)\) must equal total \((\d+)\)/, (m) => `Aniq summalar yig'indisi (${fmt(+m[1])}) umumiy summaga (${fmt(+m[2])}) teng emas.`],
    [/Percentages must add up to 100, got (.+)/, (m) => `Foizlar yig'indisi 100 bo'lishi kerak (hozir: ${m[1]}).`],
    [/Exact amounts must be whole numbers|Exact split requires integer/, () => "Aniq summalar butun son bo'lishi kerak."],
    [/Exact amounts cannot be negative/, () => "Summa manfiy bo'lishi mumkin emas."],
    [/(Percentage|Share) must be positive/, () => "Qiymatlar musbat bo'lishi kerak."],
    [/Amount must be positive/, () => "Summa musbat bo'lishi kerak."],
  ];

  const $ = (id) => document.getElementById(id);
  const el = (tag, props = {}, ...children) => {
    const node = Object.assign(document.createElement(tag), props);
    node.append(...children);
    return node;
  };

  function fmt(amount) {
    const sign = amount < 0 ? "−" : "";
    return sign + String(Math.abs(amount)).replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " so'm";
  }
  const nameOf = (id) => (state.participants.find((p) => p.id === id) || {}).name || "?";

  function translateError(message) {
    for (const [pattern, render] of SERVER_ERRORS) {
      const match = message.match(pattern);
      if (match) return render(match);
    }
    return message;
  }

  async function postJSON(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data.detail === "string" ? data.detail : "Ma'lumotlar noto'g'ri kiritilgan.";
      throw new Error(translateError(detail));
    }
    return data;
  }

  function showError(box, message) {
    box.textContent = message;
    box.classList.toggle("d-none", !message);
  }

  function hideResults() {
    $("resultsSection").classList.add("d-none");
    showError($("calcError"), "");
  }

  // ---------- Ishtirokchilar ----------
  function addParticipant(event) {
    event.preventDefault();
    const input = $("participantName");
    const name = input.value.trim().replace(/\s+/g, " ");
    if (!name) return input.focus();
    if (state.participants.some((p) => p.name.toLowerCase() === name.toLowerCase())) {
      alert(`«${name}» allaqachon qo'shilgan.`);
      return input.select();
    }
    state.participants.push({ id: state.nextParticipantId++, name });
    input.value = "";
    input.focus();
    hideResults();
    render();
  }

  function removeParticipant(id) {
    const used = state.expenses.some(
      (e) => e.paid_by === id || e.participants.some((p) => p.user_id === id)
    );
    if (used) {
      alert(`${nameOf(id)} xarajatlarda qatnashgan. Avval o'sha xarajatlarni o'chiring.`);
      return;
    }
    state.participants = state.participants.filter((p) => p.id !== id);
    hideResults();
    render();
  }

  // ---------- Xarajat formasi ----------
  function renderExpenseForm() {
    const paidBy = $("expensePaidBy");
    const selected = paidBy.value;
    paidBy.replaceChildren(el("option", { value: "", textContent: "Tanlang" }));
    for (const p of state.participants) {
      paidBy.append(el("option", { value: p.id, textContent: p.name }));
    }
    if (state.participants.some((p) => String(p.id) === selected)) paidBy.value = selected;

    const box = $("expenseShares");
    const previous = new Map(
      [...box.querySelectorAll(".share-row")].map((row) => [
        row.dataset.id,
        { checked: row.querySelector("input[type=checkbox]").checked, value: row.querySelector("input[type=number]").value },
      ])
    );
    const splitType = $("expenseSplitType").value;
    box.replaceChildren();
    for (const p of state.participants) {
      const prev = previous.get(String(p.id));
      const checkbox = el("input", {
        type: "checkbox",
        className: "form-check-input m-0",
        id: `share-${p.id}`,
        checked: prev ? prev.checked : true,
      });
      const value = el("input", {
        type: "number",
        className: "form-control form-control-sm",
        min: "0",
        step: splitType === "exact" ? "1" : "any",
        placeholder: splitType === "percentage" ? "%" : splitType === "shares" ? "ulush" : "so'm",
        value: prev ? prev.value : "",
        hidden: splitType === "equal",
      });
      value.disabled = !checkbox.checked;
      checkbox.addEventListener("change", () => (value.disabled = !checkbox.checked));
      const row = el("div", { className: "share-row" }, checkbox, el("label", { htmlFor: checkbox.id, textContent: p.name }), value);
      row.dataset.id = p.id;
      box.append(row);
    }
    if (!state.participants.length) {
      box.append(el("span", { className: "text-muted small", textContent: "Avval ishtirokchilarni qo'shing." }));
    }
    $("splitHint").textContent = SPLIT_HINTS[splitType];
  }

  function readExpenseForm() {
    const description = $("expenseDescription").value.trim();
    const amountText = $("expenseAmount").value.trim();
    const amount = Number(amountText);
    const paidBy = Number($("expensePaidBy").value);
    const splitType = $("expenseSplitType").value;

    if (state.participants.length < 2) throw new Error("Kamida 2 ta ishtirokchi qo'shing.");
    if (!amountText || !Number.isInteger(amount) || amount <= 0) throw new Error("Summani musbat butun son ko'rinishida kiriting.");
    if (!paidBy) throw new Error("Kim to'laganini tanlang.");

    const participants = [];
    for (const row of $("expenseShares").querySelectorAll(".share-row")) {
      if (!row.querySelector("input[type=checkbox]").checked) continue;
      const user_id = Number(row.dataset.id);
      if (splitType === "equal") {
        participants.push({ user_id });
        continue;
      }
      const raw = row.querySelector("input[type=number]").value.trim();
      if (raw === "" || Number(raw) < 0 || Number.isNaN(Number(raw))) {
        throw new Error(`${nameOf(user_id)} uchun qiymat kiriting.`);
      }
      participants.push({ user_id, value: raw });
    }
    if (!participants.length) throw new Error("Kamida bitta ishtirokchini belgilang.");

    return { description, amount, paid_by: paidBy, split_type: splitType, participants };
  }

  async function addExpense(event) {
    event.preventDefault();
    const errorBox = $("expenseError");
    let expense;
    try {
      expense = readExpenseForm();
      const members = state.participants.map((p) => p.id);
      const { shares } = await postJSON("/api/expenses/preview", { members, expense });
      expense.shares = shares;
    } catch (error) {
      showError(errorBox, error.message);
      return;
    }
    showError(errorBox, "");
    expense.id = state.nextExpenseId++;
    expense.description = expense.description || "Xarajat";
    state.expenses.push(expense);

    $("expenseDescription").value = "";
    $("expenseAmount").value = "";
    for (const input of $("expenseShares").querySelectorAll("input[type=number]")) input.value = "";
    $("expenseDescription").focus();
    hideResults();
    render();
  }

  function removeExpense(id) {
    state.expenses = state.expenses.filter((e) => e.id !== id);
    hideResults();
    render();
  }

  // ---------- Hisoblash ----------
  async function calculate() {
    const errorBox = $("calcError");
    if (!state.expenses.length) {
      showError(errorBox, "Avval kamida bitta xarajat qo'shing.");
      return;
    }
    try {
      const result = await postJSON("/api/calculate", {
        members: state.participants.map((p) => p.id),
        expenses: state.expenses.map(({ description, amount, paid_by, split_type, participants }) => ({
          description, amount, paid_by, split_type, participants,
        })),
      });
      showError(errorBox, "");
      renderResults(result);
    } catch (error) {
      showError(errorBox, error.message);
    }
  }

  function renderResults(result) {
    $("resultTotal").textContent = fmt(result.total);

    const list = $("transfersList");
    list.replaceChildren();
    if (!result.transfers.length) {
      list.append(el("li", { className: "settled", textContent: "Hamma hisob-kitob qilingan — hech kim qarzdor emas. 🎉" }));
    }
    for (const t of result.transfers) {
      list.append(el("li", { textContent: `${nameOf(t.from_user_id)} → ${nameOf(t.to_user_id)}: ${fmt(t.amount)}` }));
    }

    const body = $("balancesBody");
    body.replaceChildren();
    for (const m of result.members) {
      const cls = m.balance > 0 ? "pos" : m.balance < 0 ? "neg" : "";
      body.append(
        el("tr", {},
          el("td", { textContent: nameOf(m.user_id) }),
          el("td", { className: "text-end", textContent: fmt(m.paid) }),
          el("td", { className: "text-end", textContent: fmt(m.owed) }),
          el("td", { className: `text-end ${cls}`, textContent: (m.balance > 0 ? "+" : "") + fmt(m.balance) })
        )
      );
    }
    $("copyStatus").textContent = "";
    $("resultsSection").classList.remove("d-none");
    $("resultsSection").scrollIntoView({ behavior: "smooth", block: "start" });
    state.lastResult = result;
  }

  async function copyResults() {
    const r = state.lastResult;
    if (!r) return;
    const lines = ["SplitEasy — natija", `Jami xarajat: ${fmt(r.total)}`, "", "Kim kimga to'laydi:"];
    if (!r.transfers.length) lines.push("Hech kim qarzdor emas.");
    for (const t of r.transfers) lines.push(`• ${nameOf(t.from_user_id)} → ${nameOf(t.to_user_id)}: ${fmt(t.amount)}`);
    lines.push("", "Xarajatlar:");
    for (const e of state.expenses) lines.push(`• ${e.description} — ${fmt(e.amount)} (${nameOf(e.paid_by)} to'ladi)`);
    const text = lines.join("\n");
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const area = el("textarea", { value: text });
      document.body.append(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    $("copyStatus").textContent = "Nusxa olindi ✓";
  }

  function resetAll() {
    if ((state.participants.length || state.expenses.length) && !confirm("Barcha ma'lumotlar o'chiriladi. Davom etasizmi?")) return;
    state.participants = [];
    state.expenses = [];
    state.lastResult = null;
    hideResults();
    showError($("expenseError"), "");
    render();
  }

  // ---------- Ko'rsatish ----------
  function renderParticipants() {
    const list = $("participantsList");
    list.replaceChildren();
    for (const p of state.participants) {
      const remove = el("button", { type: "button", title: "O'chirish", textContent: "×" });
      remove.setAttribute("aria-label", `${p.name} ni o'chirish`);
      remove.addEventListener("click", () => removeParticipant(p.id));
      list.append(el("span", { className: "chip" }, p.name, remove));
    }
    $("participantsEmpty").classList.toggle("d-none", state.participants.length > 0);
  }

  function renderExpenses() {
    const list = $("expensesList");
    list.replaceChildren();
    for (const e of state.expenses) {
      const shares = e.shares.map((s) => `${nameOf(s.user_id)}: ${fmt(s.share_amount)}`).join(", ");
      const remove = el("button", { type: "button", className: "btn btn-sm btn-outline-danger", textContent: "O'chirish" });
      remove.addEventListener("click", () => removeExpense(e.id));
      list.append(
        el("div", { className: "expense-item" },
          el("div", {},
            el("div", { className: "fw-semibold", textContent: e.description }),
            el("div", { className: "meta", textContent: `${nameOf(e.paid_by)} to'ladi · ${SPLIT_LABELS[e.split_type]}` }),
            el("div", { className: "meta", textContent: shares })
          ),
          el("div", { className: "text-end d-flex flex-column gap-2 align-items-end" },
            el("span", { className: "amount", textContent: fmt(e.amount) }),
            remove
          )
        )
      );
    }
  }

  function render() {
    renderParticipants();
    renderExpenseForm();
    renderExpenses();
  }

  $("participantForm").addEventListener("submit", addParticipant);
  $("expenseForm").addEventListener("submit", addExpense);
  $("expenseSplitType").addEventListener("change", renderExpenseForm);
  $("toggleAll").addEventListener("click", () => {
    const boxes = [...$("expenseShares").querySelectorAll("input[type=checkbox]")];
    const check = boxes.some((b) => !b.checked);
    for (const b of boxes) {
      b.checked = check;
      b.dispatchEvent(new Event("change"));
    }
  });
  $("calculateBtn").addEventListener("click", calculate);
  $("resetBtn").addEventListener("click", resetAll);
  $("copyBtn").addEventListener("click", copyResults);
  window.addEventListener("beforeunload", (event) => {
    if (state.participants.length || state.expenses.length) event.preventDefault();
  });

  render();
})();
