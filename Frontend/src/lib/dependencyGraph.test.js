import cytoscape from "cytoscape";
import { describe, expect, it } from "vitest";
import { attachDirectoryGroups, buildDependencyElements } from "./dependencyGraph";

describe("dependency graph Cytoscape pipeline", () => {
  it("lays out verified file nodes before adding module clusters", async () => {
    const graph = {
      nodes: [
        { id: "src/a.js", label: "a.js", directory: "src", language: "JavaScript" },
        { id: "src/b.js", label: "b.js", directory: "src", language: "JavaScript" },
        { id: "lib/c.js", label: "c.js", directory: "lib", language: "JavaScript" },
      ],
      edges: [
        { source: "src/a.js", target: "src/b.js", import_name: "./b.js", verified: true },
        { source: "src/b.js", target: "missing.js", import_name: "./missing.js", verified: true },
        { source: "lib/c.js", target: "src/a.js", import_name: "../src/a.js", verified: false },
      ],
    };
    const { fileElements, edgeElements, directoryElements } = buildDependencyElements(graph);
    expect(fileElements).toHaveLength(3);
    expect(edgeElements).toHaveLength(1);
    expect(directoryElements).toHaveLength(2);
    expect(fileElements.every(({ data }) => !data.parent)).toBe(true);

    const cy = cytoscape({ headless: true, elements: [...fileElements, ...edgeElements] });
    await new Promise((resolve) => {
      const layout = cy.layout({ name: "cose", animate: false, padding: 35, nodeRepulsion: 7000, idealEdgeLength: 100 });
      layout.one("layoutstop", resolve);
      layout.run();
    });
    expect(cy.nodes().every((node) => Number.isFinite(node.position("x")) && Number.isFinite(node.position("y")))).toBe(true);

    attachDirectoryGroups(cy, fileElements, directoryElements);
    expect(cy.nodes().filter((node) => !node.data("isDirectory"))).toHaveLength(3);
    expect(cy.nodes().filter((node) => node.data("isDirectory"))).toHaveLength(2);
    expect(cy.edges()).toHaveLength(1);
    expect(cy.elements()).toHaveLength(6);
    expect(cy.getElementById("src/a.js").parent().id()).toBe("directory:src");
    cy.destroy();
  });
});
