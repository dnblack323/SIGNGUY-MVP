import { layoutDayItems, minutesWithinDay } from "@/components/schedule/scheduleModel";

/*
 * Day-view placement must follow the clock on the wall, not elapsed time since midnight.
 *
 * The viewer's zone is simulated for this suite only: the local Date getters the
 * schedule model reads are answered from real America/New_York zone data via Intl,
 * so the result is the same whatever zone the machine or CI runner uses.
 */
const ZONE = "America/New_York";
const zoneParts = new Intl.DateTimeFormat("en-US", {
  timeZone: ZONE, hourCycle: "h23", year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "numeric",
});

function partsInZone(date) {
  const parts = Object.fromEntries(zoneParts.formatToParts(date).map(({ type, value }) => [type, Number(value)]));
  return { year: parts.year, month: parts.month - 1, day: parts.day, hour: parts.hour % 24, minute: parts.minute };
}

const LOCAL_GETTERS = { getFullYear: "year", getMonth: "month", getDate: "day", getHours: "hour", getMinutes: "minute" };

describe(`Single Day positioning across daylight-saving changes (${ZONE})`, () => {
  beforeEach(() => { // per test: the CRA preset resets mocks before each test
    for (const [getter, field] of Object.entries(LOCAL_GETTERS)) {
      jest.spyOn(Date.prototype, getter).mockImplementation(function zoned() { return partsInZone(this)[field]; });
    }
  });
  afterEach(() => jest.restoreAllMocks());

  test.each([
    ["spring forward (23-hour day)", "2026-03-08", "2026-03-08T13:00:00Z", "2026-03-08T15:30:00Z"], // 9:00-11:30 AM EDT
    ["fall back (25-hour day)", "2026-11-01", "2026-11-01T14:00:00Z", "2026-11-01T16:30:00Z"], // 9:00-11:30 AM EST
    ["ordinary day", "2026-08-14", "2026-08-14T13:00:00Z", "2026-08-14T15:30:00Z"], // 9:00-11:30 AM EDT
  ])("%s: a 9:00 AM event is placed at 9:00", (_label, dateKey, start, end) => {
    expect(new Date(start).getHours()).toBe(9); // the simulated zone is active
    expect(minutesWithinDay(start, dateKey)).toBe(9 * 60);
    expect(minutesWithinDay(end, dateKey)).toBe(11 * 60 + 30);
    const [placed] = layoutDayItems([{ id: "a", start_at: start, end_at: end }], dateKey);
    expect(placed.top).toBe(540);
    expect(placed.height).toBe(150);
  });

  test("events that cross midnight are clamped to the displayed day", () => {
    expect(minutesWithinDay("2026-11-01T03:00:00Z", "2026-11-01")).toBe(0); // Oct 31, 11 PM EDT
    expect(minutesWithinDay("2026-11-02T05:00:00Z", "2026-11-01")).toBe(1440); // Nov 2, midnight EST
    const [overnight] = layoutDayItems([{ id: "b", start_at: "2026-11-01T03:00:00Z", end_at: "2026-11-01T07:00:00Z" }], "2026-11-01");
    expect(overnight.top).toBe(0); // Oct 31, 11 PM EDT
    expect(overnight.bottom).toBe(120); // Nov 1, 2:00 AM EST
  });
});
