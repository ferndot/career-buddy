// GrapesJS setup. The canvas is locked to five ATS-safe block types: section card, heading, paragraph, bullet list and
// list item. Text can be edited inside a block; blocks cannot be dragged, cloned, dropped into, or joined by anything else.
// Everything GrapesJS-specific lives here; edit.js only supplies HTML and the save handlers.
(() => {
  const ALLOWED = new Set(["cg-section", "cg-heading", "cg-paragraph", "cg-list", "cg-item", "textnode"]);
  const KEEP_ATTRS = new Set(["data-cg", "data-fact", "data-field", "data-ph", "data-parent", "data-kind"]);
  const LOCK = { draggable: false, droppable: false, copyable: false, removable: false, layerable: false };
  const BLOCKS = { section: false, heading: true, paragraph: true, list: false, item: true }; // name -> holds editable text
  let editor, handlers;

  const button = (command, label) => [{ attributes: { "data-cg-command": command, title: label }, label, command: `cg-${command}` }];
  const toolbars = { item: button("hide", "Hide"), list: button("add", "+ Add") };
  const oneLine = (text) => text.replace(/\s+/g, " ").trim();

  function defineTypes() {
    for (const [name, text] of Object.entries(BLOCKS)) {
      editor.Components.addType(`cg-${name}`, {
        // A label (no data-field) is part of the template: shown, not editable.
        isComponent: (el) => el.dataset?.cg === name && { type: `cg-${name}`, editable: text && !!el.dataset.field },
        ...(text ? { extend: "text", extendView: "text" } : {}),
        model: { defaults: { ...LOCK, ...(text ? {} : { editable: false }), toolbar: toolbars[name] ?? [] } },
      });
    }
  }

  // Anything that is not one of the locked types, or carries styling or scripting, is removed on the spot.
  function sanitize(component) {
    if (!ALLOWED.has(component.get("type"))) return void queueMicrotask(() => component.remove());
    const attributes = component.getAttributes();
    const kept = Object.fromEntries(Object.entries(attributes).filter(([key]) => KEEP_ATTRS.has(key)));
    if (Object.keys(kept).length !== Object.keys(attributes).length) component.setAttributes(kept);
    if (Object.keys(component.getStyle()).length) component.setStyle({});
  }

  // Text fields are single-line plain text: paste inserts text only, Enter does nothing, drops are ignored.
  function guardFrame() {
    const doc = editor.Canvas.getDocument();
    const editing = (e) => e.target.closest?.("[contenteditable]");
    doc.addEventListener("paste", (e) => {
      if (!editing(e)) return;
      e.preventDefault();
      doc.execCommand("insertText", false, oneLine(e.clipboardData?.getData("text/plain") ?? ""));
    }, true);
    doc.addEventListener("keydown", (e) => { if (e.key === "Enter" && editing(e)) e.preventDefault(); }, true);
    for (const type of ["drop", "dragover"]) doc.addEventListener(type, (e) => e.preventDefault(), true);
  }

  async function commit(component, text) {
    const attributes = component.getAttributes();
    const list = component.parent();
    if (!text && !attributes["data-fact"]) return void component.remove(); // a new item left empty
    const saved = await handlers.onEdit({
      id: attributes["data-fact"], field: attributes["data-field"], text,
      parent: list?.getAttributes()["data-parent"], kind: list?.getAttributes()["data-kind"],
    });
    if (saved) component.addAttributes({ "data-fact": saved });
  }

  // Replace whatever the browser left inside a field with one plain text node.
  function rewrite(component, text) {
    component.components([{ type: "textnode", content: text }]);
    component.set("cgText", text);
  }

  function defineCommands() {
    editor.Commands.add("cg-hide", {
      run: async (ed) => {
        const item = ed.getSelected();
        if (item && (!item.getAttributes()["data-fact"] || await handlers.onHide(item.getAttributes()["data-fact"]))) item.remove();
      },
    });
    editor.Commands.add("cg-add", {
      run: (ed) => {
        const list = ed.getSelected();
        const kind = list?.getAttributes()["data-kind"];
        if (!kind) return;
        const [item] = list.append({
          type: "cg-item", tagName: "li", editable: true,
          attributes: { "data-cg": "item", "data-field": kind === "Skill" ? "skill" : "bullet", "data-ph": `New ${kind === "Skill" ? "skill" : "bullet"}` },
        });
        ed.select(item);
        item.getView().onActive?.();
      },
    });
  }

  function mount(container, onEdit, onHide) {
    handlers = { onEdit, onHide };
    editor = grapesjs.init({
      container,
      height: "70vh",
      fromElement: false,
      storageManager: false,
      panels: { defaults: [] },
      blockManager: { blocks: [] },
      styleManager: { sectors: [] },
      deviceManager: { devices: [] },
      keymaps: { defaults: {} },
      richTextEditor: { actions: [] },
      avoidInlineStyle: true,
      canvas: { styles: ["/static/app.css"] },
    });
    defineTypes();
    defineCommands();
    editor.on("component:add", sanitize);
    editor.on("rte:enable", (view) => view.model.set("cgText", oneLine(view.el.textContent)));
    editor.on("rte:disable", (view) => {
      const text = oneLine(view.el.textContent);
      const changed = text !== view.model.get("cgText");
      rewrite(view.model, text);
      if (changed) commit(view.model, text);
    });
    editor.on("load", guardFrame);
    window.cg.editor = editor;
    return editor;
  }

  function show(html) {
    editor.setComponents(html);
  }

  window.cg.gjs = { mount, show };
})();
