import { layoutDayItems, minutesWithinDay } from "@/components/schedule/scheduleModel";

// Day-view placement must follow the clock on the wall, not elapsed time since midnight.
describe("Single Day positioning across daylight-saving changes", () => {
  const originalTz = process.env.TZ;
  beforeAll(() => { process.env.TZ = "America/New_York"; });
  afterAll(() => { process.env.TZ = originalTz; });

  test.each([
    ["spring forward (23-hour day)", "2026-03-08", "2026-03-08T13:00:00Z", "2026-03-08T15:30:00Z"], // 9:00-11:30 AM EDT
    ["fall back (25-hour day)", "2026-11-01", "2026-11-01T14:00:00Z", "2026-11-01T16:30:00Z"], // 9:00-11:30 AM EST
    ["ordinary day", "2026-08-14", "2026-08-14T13:00:00Z", "2026-08-14T15:30:00Z"], // 9:00-11:30 AM EDT
  ])("%s: a 9:00 AM event is placed at 9:00", (_label, dateKey, start, end) => {
    expect(new Date(start).getHours()).toBe(9); // the time zone switch is active
    expect(minutesWithinDay(start, dateKey)).toBe(9 * 60);
    expect(minutesWithinDay(end, dateKey)).toBe(11 * 60 + 30);
    const [placed] = layoutDayItems([{ id: "a", start_at: start, end_at: end }], dateKey);
    expect(placed.top).toBe(540);
    expect(placed.height).toBe(150);
  });

  test("events that cross midnight are clamped to the displayed day", () => {
    expect(minutesWithinDay("2026-11-01T03:00:00Z", "2026-11-01")).toBe(0); // Oct 31, 11 PM EDT
    expect(minutesWithinDay("2026-11-02T05:00:00Z", "2026-11-01")).toBe(1440); // Nov 2, midnight EST
  });
});
