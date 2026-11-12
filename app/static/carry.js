// Mehmon rejimida kiritilgan tezkor hisobni ro'yxatdan o'tgandan / kirgandan
// keyin profilga saqlaydi. app.js mehmon "Ro'yxatdan o'tish" yoki "Kirish"ga
// o'tganda sahifani sessionStorage'ga yozib qo'yadi; bu yerda u bazaga
// yuboriladi. Tezkor hisob sahifasining o'zi buni app.js'da bajaradi.
(() => {
  "use strict";
  const CARRY_KEY = "spliteasy:guest-carry";
  if (document.querySelector("script[data-signed-in]")) return; // index: app.js

  let carry;
  try {
    const raw = sessionStorage.getItem(CARRY_KEY);
    carry = raw ? JSON.parse(raw) : null;
  } catch (error) {
    return;
  }
  if (!carry || !(carry.participants?.length || carry.expenses?.length)) return;

  function notice(text) {
    const main = document.querySelector("main");
    if (!main) return;
    const box = document.createElement("div");
    box.className = "alert alert-success shadow-sm";
    box.setAttribute("role", "status");
    box.append(text + " ");
    const link = Object.assign(document.createElement("a"), { href: "/", textContent: "Tezkor hisobni ochish" });
    box.append(link);
    main.prepend(box);
  }

  (async () => {
    try {
      const response = await fetch("/api/quick-split/draft");
      if (!response.ok) return;
      const saved = await response.json();
      if (saved.participants.length || saved.expenses.length) {
        // The account already has a calculation: the quick split page asks
        // which one to keep, so the carried copy stays until then.
        notice("Mehmon rejimida kiritgan hisobingiz saqlanishga tayyor.");
        return;
      }
      const put = await fetch("/api/quick-split/draft", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(carry),
      });
      if (!put.ok) return;
      sessionStorage.removeItem(CARRY_KEY);
      notice("Mehmon rejimida kiritgan hisobingiz profilingizga saqlandi.");
    } catch (error) {
      /* offline: try again on the next page */
    }
  })();
})();
