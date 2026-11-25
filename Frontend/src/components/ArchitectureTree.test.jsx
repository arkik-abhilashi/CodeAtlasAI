import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ArchitectureTree from "./ArchitectureTree";

const files = [
  { path: "index.js", language: "JavaScript", size: 90, analysis: { imports: [{ name: "./lib/application", line: 1 }], exports: [{ name: "createApplication", line: 1 }], functions: [] } },
  { path: "lib/application.js", language: "JavaScript", size: 140, analysis: { imports: [{ name: "./router", line: 1 }], exports: [], classes: [{ name: "Application", line: 2 }], functions: [] } },
  { path: "lib/router/index.js", language: "JavaScript", size: 70, analysis: { imports: [], exports: [], functions: [{ name: "router", line: 1 }] } },
  { path: "examples/hello.js", language: "JavaScript", size: 55, analysis: { imports: [], exports: [], functions: [] } },
  { path: "test/app.test.js", language: "JavaScript", size: 66, analysis: { imports: [], exports: [], functions: [] } },
  { path: "package.json", language: null, size: 30, analysis: {} },
];
const edges = [
  { source: "index.js", target: "lib/application.js", verified: true },
  { source: "lib/application.js", target: "lib/router/index.js", verified: true },
  { source: "examples/hello.js", target: "lib/application.js", verified: false },
];

describe("ArchitectureTree", () => {
  it("keeps Express-like root, modules, examples, tests, and root files in hierarchy", () => {
    render(<ArchitectureTree files={files} edges={edges} entryPoints={["index.js"]} repositoryName="express" onOpenFile={vi.fn()} />);
    expect(screen.getByText("express", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText("index.js")).toBeInTheDocument();
    expect(screen.getByText("package.json")).toBeInTheDocument();
    expect(screen.getByText("lib")).toBeInTheDocument();
    expect(screen.getByText("examples")).toBeInTheDocument();
    expect(screen.getByText("test")).toBeInTheDocument();
    expect(screen.getByText("ENTRY")).toBeInTheDocument();
  });

  it("expands nested modules, inspects verified dependencies, and opens selected files", () => {
    const openFile = vi.fn();
    render(<ArchitectureTree files={files} edges={edges} entryPoints={["index.js"]} repositoryName="express" onOpenFile={openFile} />);
    fireEvent.click(screen.getByRole("button", { name: "Expand lib" }));
    fireEvent.click(screen.getByRole("button", { name: "Expand router" }));
    expect(screen.getAllByText("index.js").length).toBeGreaterThan(1);
    fireEvent.click(screen.getByText("lib", { selector: ".ca-arch-name" }).closest("button"));
    expect(screen.getByText("2 files · 1 child modules")).toBeInTheDocument();
    expect(screen.getByText("index.js", { selector: ".ca-arch-related" })).toBeInTheDocument();
    const file = screen.getByText("application.js", { selector: ".ca-arch-name" }).closest("button");
    fireEvent.doubleClick(file);
    expect(openFile).toHaveBeenCalledWith("lib/application.js");
  });
});
