import { afterEach, describe, expect, it, vi } from "vitest";
import { bindGraphGestures } from "./graphGestures";

function setup(mode = "hand") {
  const element = document.createElement("div");
  document.body.append(element);
  element.getBoundingClientRect = () => ({ left: 10, top: 20 });
  const cy = { panBy: vi.fn(), zoom: vi.fn(() => 1) };
  const modeRef = { current: mode };
  const unbind = bindGraphGestures(cy, element, modeRef);
  return { element, cy, modeRef, unbind };
}

afterEach(() => { document.body.replaceChildren(); });

describe("Full Dependency Graph gestures", () => {
  it("routes two-axis trackpad scroll to viewport pan, never node movement", () => {
    const { element, cy, unbind } = setup();
    const event = new WheelEvent("wheel", { deltaX: 24, deltaY: -36, cancelable: true });
    element.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    expect(cy.panBy).toHaveBeenCalledWith({ x: -24, y: 36 });
    expect(cy.zoom).not.toHaveBeenCalled();
    unbind();
  });

  it("routes pinch wheel gestures to anchored viewport zoom", () => {
    const { element, cy, unbind } = setup("select");
    element.dispatchEvent(new WheelEvent("wheel", { deltaY: -20, ctrlKey: true, clientX: 80, clientY: 90, cancelable: true }));
    expect(cy.zoom).toHaveBeenCalledWith({ level: expect.closeTo(Math.exp(0.2)), renderedPosition: { x: 70, y: 70 } });
    expect(cy.panBy).not.toHaveBeenCalled();
    unbind();
  });

  it("hand mode pans from a pointer drag that starts anywhere on the canvas", () => {
    const { element, cy, unbind } = setup();
    element.dispatchEvent(new PointerEvent("pointerdown", { pointerId: 1, button: 0, clientX: 30, clientY: 50, bubbles: true, cancelable: true }));
    element.dispatchEvent(new PointerEvent("pointermove", { pointerId: 1, clientX: 48, clientY: 65, bubbles: true, cancelable: true }));
    expect(cy.panBy).toHaveBeenCalledWith({ x: 18, y: 15 });
    unbind();
  });

  it("two-pointer pinch in hand mode pans the centroid and zooms", () => {
    const { element, cy, unbind } = setup();
    element.dispatchEvent(new PointerEvent("pointerdown", { pointerId: 1, button: 0, clientX: 30, clientY: 50, bubbles: true, cancelable: true }));
    element.dispatchEvent(new PointerEvent("pointerdown", { pointerId: 2, button: 0, clientX: 70, clientY: 50, bubbles: true, cancelable: true }));
    element.dispatchEvent(new PointerEvent("pointermove", { pointerId: 2, clientX: 90, clientY: 60, bubbles: true, cancelable: true }));
    expect(cy.panBy).toHaveBeenCalledWith({ x: 10, y: 5 });
    expect(cy.zoom).toHaveBeenLastCalledWith({ level: expect.closeTo(Math.hypot(60, 10) / 40), renderedPosition: { x: 50, y: 35 } });
    unbind();
  });

  it("does not intercept pointer drags in Select mode", () => {
    const { element, cy, unbind } = setup("select");
    element.dispatchEvent(new PointerEvent("pointerdown", { pointerId: 1, button: 0, clientX: 30, clientY: 50, bubbles: true, cancelable: true }));
    element.dispatchEvent(new PointerEvent("pointermove", { pointerId: 1, clientX: 48, clientY: 65, bubbles: true, cancelable: true }));
    expect(cy.panBy).not.toHaveBeenCalled();
    unbind();
  });
});
