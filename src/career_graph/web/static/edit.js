// Step 2: the profile as cards of editable blocks (shown by gjs.js). Autosave on blur, hide with Undo, merge duplicates.
(() => {
  const { $, esc, call, json, toast, hooks } = cg;
  const ATTRIBUTE_FIELDS = new Set(["headline", "location", "summary", "school", "dates"]); // everything else is a fact title
  const facts = new Map(); // id -> attributes, as last read from the server
  let mounted = false;
  let person = ""; // the profile's own fact id: new positions and education hang off it

  const field = (tag, kind, id, name, text, hint = "") =>
    `<${tag} data-cg="${kind}" data-fact="${esc(id)}" data-field="${name}" data-ph="${esc(hint)}">${esc(text)}</${tag}>`;
  const label = (tag, text) => `<${tag} data-cg="heading">${esc(text)}</${tag}>`;
  const card = (...parts) => `<section data-cg="section">${parts.join("")}</section>`;
  const list = (parent, kind, items) =>
    `<ul data-cg="list" data-parent="${esc(parent)}" data-kind="${kind}">${items.join("")}</ul>`;

  function period(attrs) {
    if (attrs.period) return attrs.period;
    return attrs.started ? `${attrs.started} - ${attrs.finished || "Present"}` : attrs.finished || "";
  }

  function cards(profile) {
    const person = profile.id;
    const own = facts.get(person) ?? {};
    const out = [card(
      field("h1", "heading", person, "title", profile.name, "Your name"),
      ...["headline", "location", "summary"].map((key) => field("p", "paragraph", person, key, own[key] ?? "", key[0].toUpperCase() + key.slice(1))),
    )];
    for (const pos of profile.positions) {
      out.push(card(
        field("h2", "heading", pos.id, "title", pos.title, "Job title"),
        ...(pos.organization_id ? [field("p", "paragraph", pos.organization_id, "organization", pos.organization, "Organization")] : []),
        field("p", "paragraph", pos.id, "dates", period(pos.attributes), "Dates, e.g. Mar 2019 - Present"),
        list(pos.id, "Achievement", pos.achievements.map((text, i) => field("li", "item", pos.achievement_ids[i], "bullet", text))),
      ));
    }
    for (const edu of profile.education) {
      out.push(card(
        field("h2", "heading", edu.id, "degree", edu.degree, "Degree"),
        edu.school_id ? field("p", "paragraph", edu.school_id, "organization", edu.school, "School") : field("p", "paragraph", edu.id, "school", edu.school, "School"),
      ));
    }
    out.push(card(label("h2", "Skills"), list(person, "Skill", profile.skills.map((text, i) => field("li", "item", profile.skill_ids[i], "skill", text)))));
    return out.join("");
  }

  async function patch(id, body) {
    const saved = await (await call(`/api/facts/${id}`, json("PATCH", body))).json();
    facts.set(id, saved.attributes);
    return saved;
  }

  // Called by the editor when a field is left. Resolves to the new fact id for a freshly added item.
  async function onEdit({ id, field: name, text, parent, kind }) {
    try {
      if (!id) {
        const created = await (await call("/api/facts", json("POST", { kind, title: text, parent_id: parent }))).json();
        facts.set(created.id, {});
        $("edit-status").textContent = "Saved";
        return created.id;
      }
      if (!ATTRIBUTE_FIELDS.has(name)) await patch(id, { title: text });
      else {
        const attrs = { ...facts.get(id) };
        if (name === "dates") { delete attrs.started; delete attrs.finished; attrs.period = text; } else attrs[name] = text;
        if (!text) delete attrs[name === "dates" ? "period" : name];
        await patch(id, { attributes: attrs });
      }
      $("edit-status").textContent = "Saved";
    } catch (err) {
      $("edit-status").textContent = `Not saved: ${err.message}`;
      load(); // put the stored text back
    }
  }

  // Hide a fact, with Undo. Resolves true when it was hidden.
  async function onHide(id) {
    try {
      await patch(id, { attributes: { ...facts.get(id), hidden: "true" } });
    } catch (err) {
      $("edit-status").textContent = `Not hidden: ${err.message}`;
      return false;
    }
    toast("Hidden.", "Undo", async () => {
      const { hidden, ...rest } = facts.get(id);
      await patch(id, { attributes: rest });
      load();
    });
    return true;
  }

  async function showDuplicates() {
    const found = await (await call("/api/duplicates")).json();
    $("dups").innerHTML = found.map((d, i) =>
      `<div class="dup"><span>Possible duplicate ${esc(d.kind)}: <strong>${esc(d.a.title)}</strong> and <strong>${esc(d.b.title)}</strong></span>` +
      `<button data-merge="${i}">Merge</button><button class="ghost" data-keep="${i}">Not the same</button></div>`).join("");
    $("dups").querySelectorAll("[data-merge]").forEach((b) => {
      const { a, b: other } = found[b.dataset.merge];
      b.onclick = async () => {
        await call("/api/merges", json("POST", { alias_id: other.id, canonical_id: a.id }));
        toast(`Merged "${other.title}" into "${a.title}".`, "Undo", async () => {
          await call("/api/merges", json("POST", { alias_id: other.id, canonical_id: a.id, undo: true }));
          load();
        });
        load();
      };
    });
    $("dups").querySelectorAll("[data-keep]").forEach((b) => {
      b.onclick = async () => {
        const { a, b: other } = found[b.dataset.keep];
        await call("/api/duplicates/dismiss", json("POST", { a_id: a.id, b_id: other.id })); // the server remembers it
        showDuplicates();
      };
    });
  }

  // "Add a position" and "Add education": new facts under the person. Bullets go in one per line, in order.
  const val = (id) => $(id).value.trim();
  async function add(make) {
    $("edit-status").textContent = "Adding...";
    try {
      const create = async (kind, title, parent, attributes = {}) =>
        (await (await call("/api/facts", json("POST", { kind, title, parent_id: parent, attributes }))).json()).id;
      await make(create, person);
      document.querySelectorAll("#add-forms input, #add-forms textarea").forEach((el) => { el.value = ""; });
      document.querySelectorAll("#add-forms details").forEach((d) => { d.open = false; });
      $("edit-status").textContent = "Saved";
      await load();
    } catch (err) {
      $("edit-status").textContent = `Not saved: ${err.message}`;
    }
  }
  $("pos-save").onclick = () => add(async (create, parent) => {
    const id = await create("Position", val("pos-title"), parent, { organization: val("pos-org"), period: val("pos-dates") });
    for (const line of val("pos-bullets").split("\n").map((l) => l.trim()).filter(Boolean)) await create("Achievement", line, id);
  });
  $("edu-save").onclick = () => add((create, parent) => create("Education", val("edu-degree") || val("edu-school"), parent, { school: val("edu-school") }));

  async function load() {
    const [profile, all] = await Promise.all([call("/api/profile").then((r) => r.json()), call("/api/facts").then((r) => r.json())]);
    facts.clear();
    all.forEach((f) => facts.set(f.id, f.attributes));
    const empty = !profile.id;
    $("edit-empty").hidden = !empty;
    $("gjs").hidden = $("add-forms").hidden = empty;
    person = profile.id;
    if (empty) return;
    if (!mounted) { cg.gjs.mount($("gjs"), onEdit, onHide); mounted = true; }
    cg.gjs.show(cards(profile));
    await showDuplicates();
  }

  hooks.edit = load;
})();
