// Step 1: the sources list, a file drop zone and "paste text instead". After an import the page goes straight to the explorer.
(() => {
  const { $, esc, call, json, say, toast, go } = cg;
  const LINKEDIN = ["zip", "csv"];
  let busy = false;

  async function importFile(file) {
    const extension = file.name.split(".").pop().toLowerCase();
    const form = new FormData();
    form.append("file", file);
    const url = LINKEDIN.includes(extension) ? "/api/import/linkedin" : "/api/import/file";
    return (await call(url, { method: "POST", body: form })).json();
  }

  async function run(label, action) {
    if (busy) return;
    busy = true;
    $("paste-btn").disabled = true;
    say("import-status", `Reading ${label}...`, "busy");
    try {
      const { facts } = await action();
      say("import-status", `Imported ${facts} facts.`, "done");
      go("edit");
    } catch (err) {
      say("import-status", `We couldn't import ${label}. ${err.message}`, "error");
    } finally {
      busy = false;
      $("paste-btn").disabled = false;
    }
  }

  // The sources list, plus a way straight back for someone who already has a profile.
  async function loadSources() {
    const [sources, profile] = await Promise.all([call("/api/sources").then((r) => r.json()), call("/api/profile").then((r) => r.json())]);
    const list = $("source-list");
    $("sources-empty").hidden = sources.length > 0;
    list.innerHTML = sources.map((s) => `<li><span>${esc(s.source)}</span> <small class="muted">${s.facts} facts</small>
      <button class="ghost" data-remove="${esc(s.source)}" aria-label="Remove ${esc(s.source)}">Remove</button></li>`).join("");
    list.querySelectorAll("[data-remove]").forEach((b) => { b.onclick = () => removeSource(b.dataset.remove); });
    $("import-existing").hidden = !profile.id;
    $("existing-name").textContent = profile.name ?? "";
    $("drop").classList.toggle("primary", !profile.id); // one main action at a time
  }

  async function removeSource(source) {
    try {
      await call(`/api/sources/${encodeURIComponent(source)}`, { method: "DELETE" });
      toast(`Removed ${source}`);
    } catch (err) {
      say("import-status", `We couldn't remove ${source}. ${err.message}`, "error");
    }
    loadSources();
  }
  cg.hooks.import = loadSources;
  loadSources().catch(() => {});

  const drop = $("drop");
  $("import-file").onchange = (e) => { const [file] = e.target.files; if (file) run(file.name, () => importFile(file)); e.target.value = ""; };
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = (e) => {
    e.preventDefault();
    drop.classList.remove("over");
    const [file] = e.dataTransfer.files;
    if (file) run(file.name, () => importFile(file));
  };
  $("paste-btn").onclick = () => {
    const text = $("paste-text").value;
    if (!text.trim()) return say("import-status", "Paste your resume text first.", "error");
    run("your pasted text", () => call("/api/import/text", json("POST", { text })).then((r) => r.json()));
  };
})();
