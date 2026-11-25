const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

function midpoint(points) {
  const [first, second] = points;
  return { x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 };
}

function distance(points) {
  return Math.hypot(points[1].x - points[0].x, points[1].y - points[0].y);
}

/**
 * Route trackpad/mouse wheel gestures through Cytoscape's viewport API. Browser
 * scrolling and Cytoscape's built-in wheel zoom are disabled on the graph so
 * a two-finger scroll can never grab or reposition a node.
 */
export function bindGraphGestures(cy, element, modeRef) {
  const pointers = new Map();
  let previousPoint = null;
  let previousCenter = null;
  let previousDistance = 0;

  const localPoint = (event) => {
    const rect = element.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };

  const onWheel = (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (event.ctrlKey || event.metaKey) {
      const point = localPoint(event);
      const nextZoom = clamp(cy.zoom() * Math.exp(-event.deltaY * 0.01), 0.3, 2.5);
      cy.zoom({ level: nextZoom, renderedPosition: point });
    } else {
      cy.panBy({ x: -event.deltaX, y: -event.deltaY });
    }
  };

  const onPointerDown = (event) => {
    if (modeRef.current !== "hand" || event.button !== 0) return;
    const point = localPoint(event);
    pointers.set(event.pointerId, point);
    previousPoint = point;
    if (pointers.size === 2) {
      const points = [...pointers.values()];
      previousCenter = midpoint(points);
      previousDistance = distance(points);
    }
    event.preventDefault();
    event.stopPropagation();
    element.setPointerCapture?.(event.pointerId);
  };

  const onPointerMove = (event) => {
    if (modeRef.current !== "hand" || !pointers.has(event.pointerId)) return;
    const point = localPoint(event);
    pointers.set(event.pointerId, point);
    const points = [...pointers.values()];
    if (points.length > 1) {
      const center = midpoint(points);
      const nextDistance = distance(points);
      if (previousCenter && previousDistance > 0 && nextDistance > 0) {
        cy.panBy({ x: center.x - previousCenter.x, y: center.y - previousCenter.y });
        const nextZoom = clamp(cy.zoom() * (nextDistance / previousDistance), 0.3, 2.5);
        cy.zoom({ level: nextZoom, renderedPosition: center });
      }
      previousCenter = center;
      previousDistance = nextDistance;
    } else if (previousPoint) {
      cy.panBy({ x: point.x - previousPoint.x, y: point.y - previousPoint.y });
    }
    previousPoint = point;
    event.preventDefault();
    event.stopPropagation();
  };

  const onPointerEnd = (event) => {
    if (modeRef.current !== "hand" || !pointers.has(event.pointerId)) return;
    pointers.delete(event.pointerId);
    const remaining = [...pointers.values()];
    previousPoint = remaining[0] || null;
    previousCenter = remaining.length === 2 ? midpoint(remaining) : null;
    previousDistance = remaining.length === 2 ? distance(remaining) : 0;
    event.preventDefault();
    event.stopPropagation();
  };

  element.addEventListener("wheel", onWheel, { passive: false, capture: true });
  element.addEventListener("pointerdown", onPointerDown, true);
  element.addEventListener("pointermove", onPointerMove, true);
  element.addEventListener("pointerup", onPointerEnd, true);
  element.addEventListener("pointercancel", onPointerEnd, true);

  return () => {
    element.removeEventListener("wheel", onWheel, true);
    element.removeEventListener("pointerdown", onPointerDown, true);
    element.removeEventListener("pointermove", onPointerMove, true);
    element.removeEventListener("pointerup", onPointerEnd, true);
    element.removeEventListener("pointercancel", onPointerEnd, true);
  };
}
