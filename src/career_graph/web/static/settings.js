// Settings > LLM connections: list, add, edit, test, choose the active one, delete.
(() => {
  const { $, esc, call, json, say, hooks } = cg;
  const state = { providers: [], active: null, connections: [], editing: null }; // editing: a connection id, "" when adding, null when closed
  const models = {}; // connection id -> model names from its last successful test
  const preset = (id) => state.providers.find((p) => p.id === id);
  const status = (text, kind) => say("llm-status", text, kind);

  // Mirrors the server's rule so the warning shows while typing. The server still enforces it.
  function isPrivate(value) {
    try { return /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|\[f[cd])/i.test(new URL(value).hostname); } catch { return false; }
  }

  function note(c) {
    return c.off_device ? `Resume text is sent to ${c.destination}` : "Stays on this computer";
  }

  function card(c) {
    const on = c.id === state.active;
    const actions = [
      `<button class="ghost" data-act="test">Test</button>`,
      `<button class="ghost" data-act="${on ? "off" : "activate"}">${on ? "Turn off" : "Set active"}</button>`,
      ...(c.read_only ? [`<span class="muted">Set by environment variables</span>`]
        : [`<button class="ghost" data-act="edit">Edit</button>`, `<button class="ghost" data-act="delete">Delete</button>`]),
    ];
    return `<li class="conn${on ? " active" : ""}" data-id="${esc(c.id)}">
      <p><strong>${esc(c.label)}</strong>${on ? '<span class="badge">Active</span>' : ""}</p>
      <p>${esc(preset(c.preset)?.label)} &middot; ${esc(c.base_url)}</p>
      <p class="muted">Model: ${esc(c.model)} &middot; Key: ${c.key_hint ? esc(c.key_hint) : "none"}</p>
      <p class="muted">${esc(note(c))}</p>
      <p class="result muted" role="status"></p>
      <div class="conn-actions">${actions.join("")}</div></li>`;
  }

  function render() {
    $("llm-empty").hidden = state.connections.length > 0;
    $("llm-list").innerHTML = state.connections.map(card).join("");
    const open = state.editing !== null;
    $("llm-form").hidden = !open;
    $("llm-add").hidden = open;
  }

  async function load() {
    if (!state.providers.length) {
      state.providers = await (await call("/api/llm/providers")).json();
      $("llm-preset").innerHTML = state.providers.map((p) => `<option value="${esc(p.id)}">${esc(p.label)}</option>`).join("");
    }
    const data = await (await call("/api/llm/connections")).json();
    Object.assign(state, { active: data.active, connections: data.connections });
    $("llm-keynote").hidden = data.key_store !== "file";
    render();
  }

  function refreshWarning() {
    const show = isPrivate($("llm-url").value);
    $("llm-private").hidden = !show;
    if (!show) $("llm-allow").checked = false;
  }

  // Fill the form for the chosen provider. Cloud addresses are fixed, local and custom ones can be edited.
  function applyPreset(editingConn) {
    const p = preset($("llm-preset").value);
    $("llm-hint").textContent = p.hint;
    $("llm-url").readOnly = !p.url_editable;
    if (!editingConn) { $("llm-url").value = p.base_url; $("llm-label").value = ""; $("llm-key").value = ""; }
    $("llm-key").required = p.needs_key && !editingConn?.key_hint;
    $("llm-key-note").textContent = p.needs_key ? "" : "(only if the server asks for one)";
    refreshWarning();
  }

  function openForm(conn) {
    state.editing = conn ? conn.id : "";
    $("llm-form-title").textContent = conn ? "Edit connection" : "Add a connection";
    $("llm-preset").value = conn ? conn.preset : state.providers[0].id;
    $("llm-preset").disabled = !!conn;
    applyPreset(conn);
    if (conn) {
      $("llm-url").value = conn.base_url; $("llm-label").value = conn.label; $("llm-model").value = conn.model;
      $("llm-allow").checked = conn.allow_private;
      $("llm-key-note").textContent = conn.key_hint ? `(saved as ${conn.key_hint}; leave blank to keep it. Changing the address removes it)` : "";
    } else {
      $("llm-model").value = "";
    }
    $("llm-check").hidden = !!conn;
    $("llm-models").innerHTML = (models[conn?.id] || []).map((m) => `<option value="${esc(m)}">`).join("");
    refreshWarning();
    render();
    $("llm-preset").focus();
  }

  const closeForm = () => { state.editing = null; render(); $("llm-add").focus(); };

  function draft() {
    const body = { preset: $("llm-preset").value, label: $("llm-label").value, model: $("llm-model").value, allow_private: $("llm-allow").checked };
    if (preset(body.preset).url_editable) body.base_url = $("llm-url").value;
    if ($("llm-key").value) body.api_key = $("llm-key").value;
    return body;
  }

  async function save(event) {
    event.preventDefault();
    const adding = state.editing === "";
    const body = draft();
    if (!adding) delete body.preset;
    $("llm-save").disabled = true;
    status("Saving...", "busy");
    try {
      await call(adding ? "/api/llm/connections" : `/api/llm/connections/${state.editing}`, json(adding ? "POST" : "PATCH", body));
      state.editing = null;
      await load();
      status(adding ? "Connection saved. Press Set active to use it." : "Changes saved.");
    } catch (error) {
      status(`Couldn't save. ${error.message}`, "error");
    } finally {
      $("llm-save").disabled = false;
    }
  }

  async function checkDraft() {
    status("Checking...", "busy");
    try {
      const res = await (await call("/api/llm/test", json("POST", draft()))).json();
      status(res.message, res.ok ? "" : "error");
      $("llm-models").innerHTML = res.models.map((m) => `<option value="${esc(m)}">`).join("");
    } catch (error) {
      status(error.message, "error");
    }
  }

  async function act(button) {
    const row = button.closest(".conn");
    const id = row.dataset.id;
    const conn = state.connections.find((c) => c.id === id);
    const act = button.dataset.act;
    try {
      if (act === "edit") return openForm(conn);
      if (act === "test") {
        row.querySelector(".result").textContent = "Testing...";
        const res = await (await call("/api/llm/test", json("POST", { id }))).json();
        models[id] = res.models;
        row.querySelector(".result").textContent = res.message;
        return;
      }
      if (act === "delete") {
        if (!confirm(`Delete "${conn.label}" and its saved key?`)) return;
        await call(`/api/llm/connections/${id}`, { method: "DELETE" });
        status("Connection deleted.");
      } else {
        await call("/api/llm/active", json("PUT", { id: act === "activate" ? id : null }));
        status(act === "activate" ? `${conn.label} is now active.` : "No connection is active. The offline reader is used.");
      }
      await load();
    } catch (error) {
      status(error.message, "error");
    }
  }

  $("llm-add").onclick = () => openForm(null);
  $("llm-cancel").onclick = closeForm;
  $("llm-form").onsubmit = save;
  $("llm-check").onclick = checkDraft;
  $("llm-preset").onchange = () => applyPreset(null);
  $("llm-url").oninput = refreshWarning;
  $("llm-list").onclick = (event) => { const b = event.target.closest("button[data-act]"); if (b) act(b); };
  hooks.settings = () => load().catch((error) => status(error.message, "error"));
})();
