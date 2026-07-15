import { computeDisplayScale, scaledDimensions } from "../lib/markupCoordinates";

describe("markup coordinate/resize contract (EC10 Phase 10C §7)", () => {
  test("scale is 1 when the container is at least as wide as the canvas", () => {
    expect(computeDisplayScale(1024, 1024)).toBe(1);
    expect(computeDisplayScale(1024, 1600)).toBe(1);
  });

  test("scale shrinks proportionally on a narrower container (never upscales)", () => {
    expect(computeDisplayScale(1024, 512)).toBeCloseTo(0.5);
    expect(computeDisplayScale(800, 400)).toBeCloseTo(0.5);
  });

  test("scaledDimensions round trip: width/height stay proportional to the source canvas", () => {
    const { width, height, scale } = scaledDimensions(1024, 768, 512);
    expect(scale).toBeCloseTo(0.5);
    expect(width).toBe(512);
    expect(height).toBe(384);
    // aspect ratio is preserved
    expect(width / height).toBeCloseTo(1024 / 768);
  });

  test("gracefully handles missing/zero dimensions without throwing", () => {
    expect(computeDisplayScale(0, 500)).toBe(1);
    expect(computeDisplayScale(500, 0)).toBe(1);
    expect(computeDisplayScale(undefined, undefined)).toBe(1);
  });
});
