import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { buildArchitectureScope, pathParent, ROOT_FILES } from "../lib/architectureGraph";
import { bindGraphGestures } from "../lib/graphGestures";

export default function ArchitectureDependencyExplorer({ files, edges, repositoryName, entryPoints, theme, onOpenFile }) {
  const rootPath = ".";
  const [tabs, setTabs] = useState(() => [{ path: rootPath, label: repositoryName, view: null }]);
  const [activePath, setActivePath] = useState(rootPath);
  const [selectedId, setSelectedId] = useState("");
  const [search, setSearch] = useState("");
  const [interactionMode, setInteractionMode] = useState("hand");
  const [zoomPercent, setZoomPercent] = useState(100);
  const hostRef = useRef(null); const cyRef = useRef(null); const cameraRef = useRef(new Map()); const tabViewsRef = useRef(new Map()); const selectRef = useRef(setSelectedId); const interactionModeRef = useRef(interactionMode);
  const viewStateRef = useRef(null);
  useEffect(() => { interactionModeRef.current = interactionMode; cyRef.current?.nodes().forEach((node) => interactionMode === "hand" ? node.ungrabify() : node.grabify()); }, [interactionMode]);
  useEffect(() => { viewStateRef.current = { activePath, search, selectedId, interactionMode }; }, [activePath, search, selectedId, interactionMode]);
  useEffect(() => { selectRef.current = setSelectedId; }, []);
  const model = useMemo(() => buildArchitectureScope(files, edges, activePath, entryPoints), [files, edges, activePath, entryPoints]);
  const selectedNode = model.nodes.find((node) => node.id === selectedId) || null;
  const visibleNodes = useMemo(() => model.nodes.filter((node) => !search || (node.name + " " + node.path + " " + node.language).toLowerCase().includes(search.toLowerCase())), [model.nodes, search]);
  const visibleEdges = useMemo(() => { const visibleIds = new Set(visibleNodes.map((node) => node.id)); return model.edges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target)); }, [model.edges, visibleNodes]);
  const getTitle = useCallback((path) => path === "." ? repositoryName : path === ROOT_FILES ? "Root-level files" : path.split("/").at(-1), [repositoryName]);
  const activateTab = useCallback((path) => {
    const current = viewStateRef.current;
    tabViewsRef.current.set(current.activePath, { search: current.search, selectedId: current.selectedId, interactionMode: current.interactionMode });
    setTabs((items) => items.some((tab) => tab.path === path) ? items : [...items, { path, label: path === "." ? repositoryName : path.split("/").at(-1), view: null }]);
    const next = tabViewsRef.current.get(path);
    setActivePath(path); setSearch(next?.search || ""); setSelectedId(next?.selectedId || ""); setInteractionMode(next?.interactionMode || "hand");
  }, [repositoryName]);
  const openTab = useCallback((path) => {
    if (!path || path === ROOT_FILES) return;
    activateTab(path);
  }, [activateTab]);
  const closeTab = (path) => {
    if (path === ".") return;
    const parent = pathParent(path);
    const destination = tabs.some((tab) => tab.path === parent && tab.path !== path) ? parent : ".";
    setTabs((current) => current.filter((tab) => tab.path !== path).some((tab) => tab.path === destination) ? current.filter((tab) => tab.path !== path) : [...current.filter((tab) => tab.path !== path), { path: destination, label: getTitle(destination), view: null }]);
    if (activePath === path) activateTab(destination);
  };
  const backToParent = () => { const parent = pathParent(activePath); if (parent !== null) activateTab(parent); };
  const setCamera = useCallback((path, cy) => cameraRef.current.set(path, { zoom: cy.zoom(), pan: cy.pan() }), []);
  useEffect(() => {
    if (!hostRef.current) return undefined;
    let disposed = false; let cy; let unbindGestures;
    import("cytoscape").then(({ default: cytoscape }) => {
      if (disposed || !hostRef.current) return;
    const parentNode = { data: { id: "scope-root", label: getTitle(activePath) + "\n" + model.files.length + " files", path: activePath, kind: "scope" }, position: { x: 0, y: 0 } };
    const dataNodes = visibleNodes.map((node, index) => {
      const columns = Math.min(4, Math.max(1, visibleNodes.length));
      const column = index % columns;
      return { data: { id: "module:" + node.id, label: node.name + "\n" + node.path + "\n" + node.fileCount + " files · " + node.incoming.size + " in / " + node.outgoing.size + " out", path: node.path, moduleId: node.id, kind: node.kind, fileCount: node.fileCount, language: node.language, incoming: node.incoming.size, outgoing: node.outgoing.size, entries: node.entryPoints.length }, position: { x: column * 250 - ((columns - 1) * 125), y: 190 + Math.floor(index / columns) * 145 } };
    });
    const dataEdges = visibleEdges.map((edge, index) => ({ data: { id: "module-edge:" + index + ":" + edge.source + ":" + edge.target, source: "module:" + edge.source, target: "module:" + edge.target, count: edge.count } }));
    const colors = theme === "dark" ? { text: "#eceaf2", node: "#25242b", root: "#43311e", edge: "#d8a55d", border: "#b86b19" } : { text: "#25242b", node: "#ffffff", root: "#fff0da", edge: "#a85f12", border: "#c7771c" };
    try {
      cy = cytoscape({ container: hostRef.current, elements: [parentNode, ...dataNodes, ...dataEdges], minZoom: .35, maxZoom: 2.5, userPanningEnabled: false, userZoomingEnabled: false, autoungrabify: false, boxSelectionEnabled: false,
        style: [
          { selector: "node", style: { label: "data(label)", width: 190, height: 78, shape: "round-rectangle", "background-color": colors.node, "border-color": colors.border, "border-width": 1.5, color: colors.text, "font-size": 9, "font-family": "-apple-system, sans-serif", "text-wrap": "wrap", "text-max-width": 178, "text-valign": "center", "text-halign": "center" } },
          { selector: "node[kind = 'scope']", style: { "background-color": colors.root, "border-width": 2.5, "font-size": 11, width: 210, height: 70 } },
          { selector: "node:selected", style: { "border-width": 3, "border-color": colors.border, "background-color": colors.root } },
          { selector: "edge", style: { width: "mapData(count, 1, 12, 1.6, 4)", "line-color": colors.edge, "target-arrow-color": colors.edge, "target-arrow-shape": "triangle", "target-arrow-fill": "filled", "target-distance-from-node": 8, "arrow-scale": 1.45, "curve-style": "bezier", "line-cap": "round" } },
        ],
      });
      cyRef.current = cy;
      cy.nodes().forEach((node) => interactionModeRef.current === "hand" ? node.ungrabify() : node.grabify());
      unbindGestures = bindGraphGestures(cy, hostRef.current, interactionModeRef);
      cy.on("tap", "node[kind != 'scope']", (event) => selectRef.current(event.target.data("moduleId")));
      cy.on("dbltap", "node[kind != 'scope']", (event) => { const item = model.nodes.find((node) => node.id === event.target.data("moduleId")); if (item?.kind === "module") openTab(item.id); });
      cy.on("pan zoom", () => setCamera(activePath, cy));
      cy.on("zoom", () => setZoomPercent(Math.round(cy.zoom() * 100)));
      const saved = cameraRef.current.get(activePath);
      if (saved) cy.viewport(saved); else cy.fit(cy.elements(), 50);
    } catch (error) { console.error("Architecture dependency map failed", error); }
    }).catch((error) => { if (!disposed) console.error("Cytoscape.js could not be loaded for architecture view", error); });
    return () => { disposed = true; unbindGestures?.(); if (cy) setCamera(activePath, cy); cy?.destroy(); if (cyRef.current === cy) cyRef.current = null; };
  }, [activePath, visibleNodes, visibleEdges, theme, model.nodes, model.files.length, openTab, getTitle, setCamera]);
  const selectedFiles = selectedNode?.files || [];
  const selectedPaths = new Set(selectedFiles.map((file) => file.path));
  const incoming = selectedNode ? model.verifiedEdges.filter((edge) => selectedPaths.has(edge.target) && !selectedPaths.has(edge.source)).map((edge) => edge.source) : [];
  const outgoing = selectedNode ? model.verifiedEdges.filter((edge) => selectedPaths.has(edge.source) && !selectedPaths.has(edge.target)).map((edge) => edge.target) : [];
  const breadcrumbs = activePath === "." ? ["."] : [".", ...activePath.split("/").map((_, index, parts) => parts.slice(0, index + 1).join("/"))];
  const dirs = [...new Set(files.map((file) => file.path.includes("/") ? file.path.split("/")[0] : ""))].filter(Boolean);
  const overview = repositoryName + " contains " + files.length + " indexed files across " + dirs.length + " top-level areas. This map groups source files by their real directories; arrows represent only statically verified imports (importer → dependency).";
  const fit = () => cyRef.current?.fit(cyRef.current.elements(), 45);
  const reset = () => { cameraRef.current.delete(activePath); fit(); };
  return <section className="ca-dependency-explorer">
    <header className="ca-dependency-overview"><div><span>HIERARCHICAL DEPENDENCY EXPLORER</span><small>{overview}</small><small>{model.boundaryIncoming.size} verified external importers · {model.boundaryOutgoing.size} verified external dependencies at this scope</small></div></header>
    <nav className="ca-subgraph-tabs" aria-label="Open architecture subgraphs">{tabs.map((tab) => <div key={tab.path} role="tab" aria-selected={activePath === tab.path} className={activePath === tab.path ? "is-active" : ""}><button type="button" className="ca-subgraph-tab-select" onClick={() => activateTab(tab.path)}>{tab.label}</button>{tab.path !== "." && <button type="button" className="ca-subgraph-tab-close" aria-label={"Close " + tab.label} onClick={() => closeTab(tab.path)}>×</button>}</div>)}</nav>
    <div className="ca-subgraph-breadcrumbs">{breadcrumbs.map((path, index) => <button key={path} onClick={() => activateTab(path)}>{index ? " / " : ""}{getTitle(path)}</button>)}</div>
    <div className="ca-subgraph-toolbar"><input type="search" aria-label="Search architecture modules" placeholder="Search modules" value={search} onChange={(event) => setSearch(event.target.value)} /><div className="ca-subgraph-mode-controls" role="group" aria-label="Graph interaction mode"><button type="button" aria-pressed={interactionMode === "hand"} onClick={() => setInteractionMode("hand")}>✋ Hand / Pan</button><button type="button" aria-pressed={interactionMode === "select"} onClick={() => setInteractionMode("select")}>↖ Select</button></div><button type="button" onClick={fit}>Fit</button><button type="button" onClick={reset}>Reset</button><button type="button" aria-label="Zoom out" onClick={() => cyRef.current?.zoom(Math.max(.35, cyRef.current.zoom() / 1.2))}>−</button><span>{zoomPercent}%</span><button type="button" aria-label="Zoom in" onClick={() => cyRef.current?.zoom(Math.min(2.5, cyRef.current.zoom() * 1.2))}>＋</button>{activePath !== "." && <button type="button" onClick={backToParent}>← Back to Parent</button>}</div>
    <div className="ca-subgraph-layout"><div className="ca-subgraph-canvas"><div className="ca-subgraph-cytoscape" ref={hostRef} role="application" aria-label={"Module dependencies for " + getTitle(activePath)} />{!model.nodes.length && <p className="ca-subgraph-empty">No child modules or root-level files are indexed at this path.</p>}{model.nodes.length > 0 && !visibleNodes.length && <p className="ca-subgraph-empty">No modules match this search.</p>}<div className="ca-subgraph-legend">Arrow direction: importer → dependency · {visibleEdges.length} direct module relationships</div></div>
      <aside className="ca-subgraph-inspector"><p className="ca-kicker">{selectedNode ? "MODULE INSPECTOR" : "SELECT A MODULE"}</p><h3>{selectedNode?.path || activePath}</h3>{selectedNode ? <><p>{selectedNode.fileCount} files · {selectedNode.language}</p><small>{selectedNode.childDirectories.length} immediate subdirectories · {selectedNode.entryPoints.length} detected entry points</small><h4>Structural evidence</h4><p>Directory grouping comes from repository paths. Dependency counts are based on resolved local import records.</p>{selectedNode.entryPoints.map((path) => <p className="ca-subgraph-entry" key={path}>ENTRY · {path}</p>)}<h4>Verified incoming dependencies</h4>{[...new Set(incoming)].slice(0, 60).map((path) => <button className="ca-subgraph-related" key={path} onClick={() => onOpenFile(path)}>{path}</button>)}{!incoming.length && <small>None in this scope.</small>}<h4>Verified outgoing dependencies</h4>{[...new Set(outgoing)].slice(0, 60).map((path) => <button className="ca-subgraph-related" key={path} onClick={() => onOpenFile(path)}>{path}</button>)}{!outgoing.length && <small>None in this scope.</small>}{selectedNode.kind === "root-files" && <><h4>Files in this group</h4>{selectedNode.files.slice(0, 60).map((file) => <button className="ca-subgraph-related" key={file.path} onClick={() => onOpenFile(file.path)}>{file.path}</button>)}</>}<h4>Important symbols</h4>{selectedNode.symbols.map((symbol, index) => <p className="ca-subgraph-symbol" key={symbol.file + symbol.name + index}><code>{symbol.name}</code><small>{symbol.kind} · {symbol.file}</small></p>)}{selectedNode.kind === "module" && <button className="ca-button ca-button--primary" type="button" onClick={() => openTab(selectedNode.id)}>Explore {selectedNode.name} →</button>}</> : <p>Choose a module node to inspect its files and verified incoming and outgoing dependencies. Double-click or select Explore to open a child subgraph.</p>}</aside></div>
  </section>;
}
