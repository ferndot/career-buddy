// Career explorer: the fact graph drawn with Cytoscape.js. Redrawn each time the step opens.
(() => {
  const { call, hooks } = cg;
  let cy = null;

  async function draw() {
    const graph = await (await call("/api/graph")).json();
    const elements = [
      ...graph.nodes.map((n) => ({ data: { id: n.id, label: n.title, kind: n.kind } })),
      ...graph.edges.map((e) => ({ data: { source: e.source, target: e.target, label: e.kind } })),
    ];
    if (!cy) {
      cy = cytoscape({
        container: document.getElementById("graph"),
        style: [
          { selector: "node", style: { label: "data(label)", "font-size": 10, "text-wrap": "wrap", "text-max-width": 120, "background-color": "#4a6fa5", color: "#222" } },
          { selector: "edge", style: { width: 1, "line-color": "#999", "curve-style": "bezier", "target-arrow-shape": "triangle" } },
        ],
      });
    }
    cy.resize(); // the container was hidden when it was created
    cy.elements().remove();
    cy.add(elements);
    cy.layout({ name: "breadthfirst", directed: true, padding: 10 }).run();
  }

  const load = hooks.edit; // edit.js decides empty vs. filled; the graph draws after it
  hooks.edit = async () => { await load?.(); await draw().catch(() => {}); };
})();
