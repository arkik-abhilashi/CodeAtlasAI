export function buildDependencyElements(graph) {
  const nodes = (graph?.nodes || []).filter((node) => typeof node.id === "string" && node.id.length > 0);
  const nodeIds = new Set(nodes.map((node) => node.id));
  const directories = [...new Set(nodes.map((node) => node.directory || "."))];
  const fileElements = nodes.map((node) => ({
    data: {
      id: node.id,
      label: node.label,
      language: node.language || "Other",
      directory: node.directory || ".",
      group: (node.directory || ".").split("/")[0] || "root",
      inDegree: node.in_degree || 0,
      outDegree: node.out_degree || 0,
    },
  }));
  const edgeElements = (graph?.edges || [])
    .filter((edge) => edge.verified === true && nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .map((edge, index) => ({
      data: {
        id: `edge:${index}:${edge.source}:${edge.target}`,
        source: edge.source,
        target: edge.target,
        import_name: edge.import_name,
      },
    }));
  const directoryElements = directories.map((directory) => ({
    data: {
      id: `directory:${directory}`,
      label: directory === "." ? "root" : directory,
      isDirectory: true,
    },
  }));

  return { fileElements, edgeElements, directoryElements };
}

export function attachDirectoryGroups(cy, fileElements, directoryElements) {
  cy.add(directoryElements);
  cy.batch(() => {
    fileElements.forEach(({ data }) => {
      cy.getElementById(data.id).move({ parent: `directory:${data.directory}` });
    });
  });
}
