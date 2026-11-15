// Shared helpers and step navigation. Every other script hangs its pieces off `window.cg`.
(() => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const hooks = {}; // step name -> function that runs each time the step opens

  async function call(url, options) {
    const res = await fetch(url, options).catch(() => { throw new Error("The server could not be reached"); });
    if (!res.ok) {
      const detail = (await res.json().catch(() => ({}))).detail;
      throw new Error(typeof detail === "string" ? detail : res.statusText);
    }
    return res;
  }
  const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

  // Show a message in a status line. Errors are announced at once (role=alert); progress and success politely.
  function say(id, text, state = "") {
    const el = $(id);
    el.textContent = text;
    el.dataset.state = state;
    el.setAttribute("role", state === "error" ? "alert" : "status");
  }

  let toastTimer;
  // A short message, optionally with one action button (Undo).
  function toast(message, action, run) {
    const box = $("toast");
    box.innerHTML = `<span>${esc(message)}</span>`;
    if (action) {
      const button = document.createElement("button");
      button.textContent = action;
      button.onclick = () => { box.hidden = true; run(); };
      box.append(button);
    }
    box.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { box.hidden = true; }, 8000);
  }

  function go(step) {
    for (const name of ["import", "edit", "create", "settings"]) $(`step-${name}`).hidden = name !== step;
    document.querySelectorAll("#steps button").forEach((b) => {
      if (b.dataset.step === step) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
    });
    hooks[step]?.();
  }

  document.querySelectorAll("#steps button").forEach((b) => { b.onclick = () => go(b.dataset.step); });
  document.querySelectorAll("[data-go]").forEach((b) => { b.onclick = () => go(b.dataset.go); });
  window.cg = { $, esc, call, json, say, toast, go, hooks };
  go("import");
})();
