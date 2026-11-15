// Step 1: a file drop zone and "paste text instead". After an import the page goes straight to Edit.
(() => {
  const { $, call, json, go } = cg;
  const LINKEDIN = ["zip", "csv"];

  async function importFile(file) {
    const extension = file.name.split(".").pop().toLowerCase();
    const form = new FormData();
    form.append("file", file);
    const url = LINKEDIN.includes(extension) ? "/api/import/linkedin" : "/api/import/file";
    return (await call(url, { method: "POST", body: form })).json();
  }

  async function run(label, action) {
    $("import-status").textContent = `Importing ${label}...`;
    try {
      const { facts } = await action();
      $("import-status").textContent = `Imported ${facts} facts.`;
      go("edit");
    } catch (err) {
      $("import-status").textContent = err.message;
    }
  }

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
  $("paste-btn").onclick = () => run("text", () => call("/api/import/text", json("POST", { text: $("paste-text").value })).then((r) => r.json()));
})();
