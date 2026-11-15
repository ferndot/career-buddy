// Step 3: pick a template, optionally paste a job posting, preview, choose bullets, download. The ATS check is a warning.
(() => {
  const { $, esc, call, json, hooks } = cg;
  const KINDS = { resume: "Resume", letter: "Letter", other: "Other" };
  const WHY = {
    coverage: "some lines were not read back", order: "lines are out of reading order",
    name: "the name is not in the first lines", headings: "headings are missing or out of order",
    table: "it contains a table", text_box: "it contains a text box", header_footer: "text sits in the header or footer",
    images: "it contains images", text_layer: "a page has no text layer", glyphs: "some glyphs are unmapped",
  };
  let templates = [];
  let selection = null; // null: the template's own top bullets; otherwise a Set of bullet fact ids
  let overrides = {}; // bullet fact id -> an accepted suggestion
  let timer;

  const template = () => templates.find((t) => t.id === $("template").value);
  const request = () => ({
    template: template().id,
    job_text: $("job-text").value,
    inputs: Object.fromEntries([...document.querySelectorAll("#inputs input")].map((i) => [i.name, i.value])),
    ...(selection ? { selection: [...selection] } : {}),
    overrides,
  });
  const chips = (id, words) => { $(id).innerHTML = words.map((w) => `<span class="chip">${esc(w)}</span>`).join(""); };
  const setDownloads = (on) => document.querySelectorAll(".bar button[data-format]").forEach((b) => { b.disabled = !on; });

  function badge(codes, format) {
    const el = $("ats-badge");
    el.hidden = false;
    el.className = codes.length ? "badge warn" : "badge";
    el.textContent = codes.length ? `ATS warning: ${codes.map((c) => WHY[c] ?? c).join("; ")}` : "Passes ATS check";
    $("ats-format").textContent = format.toUpperCase();
  }

  function paper(doc) {
    const entry = (e) => (e.heading ? `<h3>${esc(e.heading.text)}</h3>` : "") + (e.paragraph ? `<p>${esc(e.paragraph.text)}</p>` : "") +
      (e.bullets.length ? `<ul>${e.bullets.map((b) => `<li>${esc(b.text)}</li>`).join("")}</ul>` : "");
    return `<h1>${esc(doc.name.text)}</h1>` + doc.intro.map((l) => `<p>${esc(l.text)}</p>`).join("") +
      doc.sections.map((s) => (s.title ? `<h2>${esc(s.title)}</h2>` : "") + s.entries.map(entry).join("")).join("");
  }

  async function showBullets(shown) {
    const profile = await (await call("/api/profile")).json();
    $("bullets").innerHTML = profile.positions.map((p) =>
      `<strong>${esc(p.title)}</strong>` + p.achievements.map((text, i) => {
        const id = p.achievement_ids[i];
        const on = selection ? selection.has(id) : shown.has(id);
        return `<label><input type="checkbox" value="${esc(id)}"${on ? " checked" : ""}> <span>${esc(text)}</span></label>`;
      }).join("")).join("");
    $("bullets").querySelectorAll("input").forEach((box) => {
      box.onchange = () => {
        selection = new Set([...$("bullets").querySelectorAll("input:checked")].map((i) => i.value));
        schedule();
      };
    });
  }

  async function refresh() {
    try {
      const out = await (await call("/api/documents/preview", json("POST", request()))).json();
      $("create-status").textContent = "";
      $("preview").innerHTML = paper(out.document);
      chips("matched", out.tailoring.matched);
      chips("missing", out.tailoring.missing);
      $("markers").innerHTML = out.markers.map((m) =>
        `<li>${m.weak ? "weak signal" : esc(m.kind)}: ${esc(m.found)}${m.replacement ? ` to ${esc(m.replacement)}` : ""}</li>`).join("");
      badge(out.ats.issues.map((i) => i.code), out.ats.format);
      setDownloads(true);
      const shown = new Set(out.document.sections.flatMap((s) => s.entries.flatMap((e) => e.bullets.map((b) => b.source_fact_id))));
      await showBullets(shown);
    } catch (err) {
      $("create-status").textContent = err.message;
      $("preview").innerHTML = "";
      $("ats-badge").hidden = true;
      setDownloads(false);
    }
  }
  const schedule = () => { clearTimeout(timer); timer = setTimeout(refresh, 250); };

  // LLM rewordings. The server only returns the ones that passed its verifier; Accept turns one into an override.
  async function suggest() {
    const box = $("suggestions");
    const say = (text) => { box.innerHTML = `<p class="muted">${esc(text)}</p>`; };
    if (!$("job-text").value.trim()) return say("Paste a job posting to get suggestions.");
    say("Asking the LLM...");
    try {
      const { suggestions } = await (await call("/api/documents/suggest", json("POST", request()))).json();
      if (!suggestions.length) return say("No rewordings to suggest.");
      box.innerHTML = "<ul>" + suggestions.map((s, i) =>
        `<li><del>${esc(s.before)}</del> <ins>${esc(s.after)}</ins> <button data-accept="${i}">Accept</button><button class="ghost" data-reject="${i}">Reject</button></li>`).join("") + "</ul>";
      box.querySelectorAll("li").forEach((li, i) => {
        li.querySelector("[data-accept]").onclick = () => { overrides[suggestions[i].fact_id] = suggestions[i].after; li.remove(); schedule(); };
        li.querySelector("[data-reject]").onclick = () => li.remove();
      });
    } catch (err) {
      say(err.message); // for example "No LLM is configured"
    }
  }

  async function download(format) {
    $("create-status").textContent = `Preparing ${format.toUpperCase()}...`;
    try {
      const res = await call("/api/documents/render", json("POST", { ...request(), format }));
      badge((res.headers.get("X-ATS-Issues") ?? "").split(",").filter(Boolean), format);
      const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? `document.${format}`;
      const link = Object.assign(document.createElement("a"), { href: URL.createObjectURL(await res.blob()), download: name });
      link.click();
      URL.revokeObjectURL(link.href);
      $("create-status").textContent = "";
    } catch (err) {
      $("create-status").textContent = err.message;
    }
  }

  function pickTemplate() {
    const t = template();
    const fields = [...t.required.map((n) => [n, true]), ...t.optional.map((n) => [n, false])];
    $("inputs").innerHTML = fields.map(([name, required]) =>
      `<label>${esc(name.replace(/_/g, " "))}${required ? "" : " (optional)"}<input type="text" name="${name}"${required ? " required" : ""}></label>`).join("");
    $("inputs").querySelectorAll("input").forEach((i) => { i.oninput = schedule; });
    selection = null;
    $("suggestions").innerHTML = ""; // they were made for the previous template
    schedule();
  }

  function pickKind() {
    const kind = $("kind").value;
    $("template").innerHTML = templates.filter((t) => t.kind === kind).map((t) => `<option value="${t.id}">${esc(t.label)}</option>`).join("");
    pickTemplate();
  }

  hooks.create = async () => {
    if (!templates.length) {
      templates = await (await call("/api/templates")).json();
      $("kind").innerHTML = [...new Set(templates.map((t) => t.kind))].map((k) => `<option value="${k}">${KINDS[k]}</option>`).join("");
      $("kind").onchange = pickKind;
      $("template").onchange = pickTemplate;
      $("job-text").oninput = schedule;
      $("suggest").onclick = suggest;
      document.querySelectorAll(".bar button[data-format]").forEach((b) => { b.onclick = () => download(b.dataset.format); });
      pickKind();
    } else {
      refresh(); // facts may have changed in Edit
    }
  };
})();
