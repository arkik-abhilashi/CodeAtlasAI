import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { buildArchitectureScope } from "../lib/architectureGraph";
import ArchitectureDependencyExplorer from "./ArchitectureDependencyExplorer";

const graphHarness = vi.hoisted(() => ({ instances: [] }));
vi.mock("cytoscape", () => ({ default: (options) => {
  const canvas = options.container.ownerDocument.createElement("canvas"); options.container.appendChild(canvas);
  const handlers = {}; let zoom = 1; let pan = { x: 0, y: 0 };
  const nodeControl = { ungrabify: vi.fn(), grabify: vi.fn() };
  const cy = {
    on: (event, selector, callback) => { handlers[event] = typeof selector === "function" ? selector : callback; },
    fit: () => cy, elements: () => [], nodes: () => ({ forEach: (callback) => callback(nodeControl) }), panBy: vi.fn(),
    zoom: (next) => { if (next !== undefined) { zoom = typeof next === "object" ? next.level : next; handlers.zoom?.(); } return zoom; },
    pan: () => pan, viewport: (view) => { if (view) { zoom = view.zoom; pan = view.pan; } return cy; },
    getElementById: () => ({ select: () => cy }), destroy: () => canvas.remove(),
  };
  graphHarness.instances.push({ options, handlers, cy, nodeControl });
  return cy;
} }));

const files = [
  { path: "index.js", language: "JavaScript", analysis: {} },
  { path: "lib/application.js", language: "JavaScript", analysis: { classes: [{ name: "Application" }] } },
  { path: "lib/router/index.js", language: "JavaScript", analysis: { functions: [{ name: "router" }] } },
  { path: "test/application.test.js", language: "JavaScript", analysis: {} },
  { path: "examples/hello.js", language: "JavaScript", analysis: {} },
  { path: "package.json", language: null, analysis: {} },
];
const edges = [
  { source: "index.js", target: "lib/application.js", verified: true },
  { source: "lib/application.js", target: "lib/router/index.js", verified: true },
  { source: "test/application.test.js", target: "lib/application.js", verified: true },
  { source: "examples/hello.js", target: "lib/router/index.js", verified: false },
];

describe("verified hierarchical dependency scopes", () => {
  it("aggregates only verified direct imports in the importer-to-dependency direction", () => {
    const root = buildArchitectureScope(files, edges, ".", ["index.js"]);
    const byId = new Map(root.nodes.map((node) => [node.id, node]));
    expect([...byId.keys()].sort()).toEqual(["@root-files", "examples", "lib", "test"]);
    expect(root.edges.map(({ source, target, count }) => ({ source, target, count }))).toEqual([{ source: "@root-files", target: "lib", count: 1 }, { source: "test", target: "lib", count: 1 }]);
    expect([...byId.get("lib").incoming]).toEqual(["index.js", "test/application.test.js"]);
    expect(byId.get("@root-files").entryPoints).toEqual(["index.js"]);
  });

  it("opens a nested scope with its own root files and only direct child relationships", () => {
    const nested = buildArchitectureScope(files, edges, "lib", ["index.js"]);
    expect(nested.nodes.map((node) => node.id).sort()).toEqual(["@root-files", "lib/router"]);
    expect(nested.edges.map(({ source, target, count }) => ({ source, target, count }))).toEqual([{ source: "@root-files", target: "lib/router", count: 1 }]);
    expect(nested.nodes.find((node) => node.id === "@root-files").files.map((file) => file.path)).toEqual(["lib/application.js"]);
  });

  it("opens unique module subgraphs and survives rapid searching without React and Cytoscape DOM conflicts", async () => {
    graphHarness.instances.length = 0;
    render(<ArchitectureDependencyExplorer files={files} edges={edges} entryPoints={["index.js"]} repositoryName="express" theme="light" onOpenFile={vi.fn()} />);
    await waitFor(() => expect(graphHarness.instances.length).toBeGreaterThan(0));
    const graphHost = screen.getByRole("application", { name: "Module dependencies for express" });
    expect(graphHost.querySelector("canvas")).toBeTruthy();
    const rootGraph = graphHarness.instances.at(-1);
    rootGraph.handlers.dbltap({ target: { data: () => "lib" } });
    await waitFor(() => expect(screen.getByRole("application", { name: "Module dependencies for lib" })).toBeInTheDocument());
    const nestedGraph = graphHarness.instances.at(-1);
    expect(nestedGraph.options.elements.find((element) => element.data.id === "scope-root").data.label).toContain("lib");
    expect(nestedGraph.options.elements.filter((element) => element.data.source).map((element) => [element.data.source, element.data.target])).toEqual([["module:@root-files", "module:lib/router"]]);
    fireEvent.click(screen.getByText("express", { selector: ".ca-subgraph-tab-select" }));
    const search = screen.getByRole("searchbox", { name: "Search architecture modules" });
    fireEvent.change(search, { target: { value: "lib" } });
    fireEvent.change(search, { target: { value: "application" } });
    fireEvent.change(search, { target: { value: "no-result" } });
    expect(screen.getByText("No modules match this search.")).toBeInTheDocument();
    fireEvent.change(search, { target: { value: "" } });
    await waitFor(() => expect(graphHarness.instances.length).toBeGreaterThanOrEqual(3));
    expect(screen.getByRole("application", { name: "Module dependencies for express" }).querySelector("canvas")).toBeTruthy();
  });

  it("uses explicit Hand and Select modes without rebuilding the module graph", async () => {
    graphHarness.instances.length = 0;
    render(<ArchitectureDependencyExplorer files={files} edges={edges} entryPoints={["index.js"]} repositoryName="express" theme="light" onOpenFile={vi.fn()} />);
    await waitFor(() => expect(graphHarness.instances.length).toBeGreaterThan(0));
    const graph = graphHarness.instances.at(-1);
    expect(graph.options.userPanningEnabled).toBe(false);
    expect(graph.options.userZoomingEnabled).toBe(false);
    expect(graph.nodeControl.ungrabify).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "↖ Select" }));
    await waitFor(() => expect(graph.nodeControl.grabify).toHaveBeenCalled());
    expect(screen.getByRole("button", { name: "↖ Select" })).toHaveAttribute("aria-pressed", "true");
    expect(graphHarness.instances.at(-1)).toBe(graph);
  });

  it("renders every module relationship as a clearly directed edge", async () => {
    graphHarness.instances.length = 0;
    render(<ArchitectureDependencyExplorer files={files} edges={edges} entryPoints={[]} repositoryName="express" theme="light" onOpenFile={vi.fn()} />);
    await waitFor(() => expect(graphHarness.instances.length).toBeGreaterThan(0));
    const edgeStyle = graphHarness.instances.at(-1).options.style.find((rule) => rule.selector === "edge").style;
    expect(edgeStyle["target-arrow-shape"]).toBe("triangle");
    expect(edgeStyle["target-arrow-fill"]).toBe("filled");
    expect(edgeStyle["target-distance-from-node"]).toBe(8);
    expect(edgeStyle["arrow-scale"]).toBeGreaterThan(1);
  });
});
