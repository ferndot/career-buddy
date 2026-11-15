// Step 3: pick a template, optionally paste a job posting, preview, choose bullets, download. The ATS check is a warning.
(() => {
  const { $, esc, call, json, say, hooks } = cg;
  const KINDS = { resume: "Resume", letter: "Letter", other: "Other" };
  // What each ATS issue means for the reader, in sentences. Codes never reach the screen.
  const WHY = {
    coverage: "Some lines did not come through when the file was read back.",
    order: "Some lines came out jumbled.",
    name: "Your name was not at the very top.",
    headings: "Some section headings were missing or in a different sequence.",
    table: "It contains a table, which many systems skip.",
    text_box: "It contains a text box, which many systems skip.",
    header_footer: "Text sits in the page header or footer, which many systems skip.",
    images: "It contains images, which software cannot read.",
    text_layer: "A page has no selectable text.",
    glyphs: "Some characters did not come through as readable text.",
  };
  const FLAGS = { strip: "Removed", swap: "Changed" };
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
    el.textContent = codes.length ? "ATS warning" : "Passes ATS check";
    $("ats-detail").hidden = !codes.length;
    $("ats-detail").innerHTML = codes.map((c) => `<li>${esc(WHY[c] ?? "Something in the file may not be read correctly.")}</li>`).join("");
    $("ats-format").textContent = `Checked as ${format.toUpperCase()}, the way software employers use reads it`;
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
      say("create-status", "");
      $("preview").innerHTML = paper(out.document);
      chips("matched", out.tailoring.matched);
      chips("missing", out.tailoring.missing);
      $("match").hidden = !$("job-text").value.trim();
      $("markers").innerHTML = out.markers.map((m) => m.kind === "flag"
        ? `<li>Check the wording: "${esc(m.found)}" is often read as a sign of machine-written text.</li>`
        : `<li>${FLAGS[m.kind] ?? "Changed"}: "${esc(m.found)}"${m.replacement ? ` to "${esc(m.replacement)}"` : ""}</li>`).join("");
      badge(out.ats.issues.map((i) => i.code), out.ats.format);
      setDownloads(true);
      const shown = new Set(out.document.sections.flatMap((s) => s.entries.flatMap((e) => e.bullets.map((b) => b.source_fact_id))));
      await showBullets(shown);
    } catch (err) {
      say("create-status", err.message, "error");
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
    say("create-status", `Preparing ${format.toUpperCase()}...`, "busy");
    try {
      const res = await call("/api/documents/render", json("POST", { ...request(), format }));
      badge((res.headers.get("X-ATS-Issues") ?? "").split(",").filter(Boolean), format);
      const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? `document.${format}`;
      const link = Object.assign(document.createElement("a"), { href: URL.createObjectURL(await res.blob()), download: name });
      link.click();
      URL.revokeObjectURL(link.href);
      say("create-status", "");
    } catch (err) {
      say("create-status", err.message, "error");
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
    const empty = !(await call("/api/profile").then((r) => r.json())).id;
    $("create-empty").hidden = !empty;
    $("create-body").hidden = empty;
    if (empty) return;
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
