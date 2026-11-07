export const DAY_MS = 24 * 60 * 60 * 1000;

// Multi-argument Date constructors interpret years 0–99 as 1900–1999.
export function localDateFromParts(year, monthIndex, day = 1) {
  const date = new Date(0);
  date.setHours(0, 0, 0, 0);
  date.setFullYear(year, monthIndex, day);
  return date;
}

function utcDateFromParts(year, monthIndex, day) {
  const date = new Date(0);
  date.setUTCHours(0, 0, 0, 0);
  date.setUTCFullYear(year, monthIndex, day);
  return date;
}

export function parseDateOnly(value) {
  const input = String(value || "").trim();
  // Date fields use YYYY-MM-DD; dashboard completion and update fields are
  // ISO timestamps. Preserve their calendar-date prefix without accepting junk.
  if (!/^\d{4}-\d{2}-\d{2}$/.test(input)) {
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?$/.test(input)
        || Number.isNaN(new Date(input).getTime())) return null;
  }
  const raw = input.slice(0, 10);
  const [yearText, monthText, dayText] = raw.split("-");
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  if (!Number.isInteger(year) || year < 1 || !Number.isInteger(month) || !Number.isInteger(day)) return null;
  const date = utcDateFromParts(year, month - 1, day);
  const time = date.getTime();
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    return null;
  }
  return {
    year,
    month,
    monthIndex: month - 1,
    day,
    iso: raw,
    dayNumber: Math.floor(time / DAY_MS),
    date,
  };
}

export function dateOnlyToDate(value) {
  const parts = parseDateOnly(value);
  return parts ? parts.date : null;
}

export function dayNumberToDate(dayNumber) {
  return new Date(dayNumber * DAY_MS);
}

export function dayNumberToIso(dayNumber) {
  const d = dayNumberToDate(dayNumber);
  const year = d.getUTCFullYear();
  if (!Number.isInteger(year) || year < 1 || year > 9999) return "";
  return `${String(year).padStart(4, "0")}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;
}

export function todayDayNumber() {
  const today = new Date();
  return Math.floor(utcDateFromParts(today.getFullYear(), today.getMonth(), today.getDate()).getTime() / DAY_MS);
}

export function startOfDateOnlyDay(value) {
  if (value instanceof Date) {
    return utcDateFromParts(value.getFullYear(), value.getMonth(), value.getDate());
  }
  return dateOnlyToDate(value);
}

export function daysBetweenDateOnly(fromDate, toDate) {
  return Math.ceil((toDate.getTime() - fromDate.getTime()) / DAY_MS);
}

// Database timestamps are UTC even when serialized without an offset.
export function formatUtcTimestamp(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const normalized = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(raw) ? `${raw}Z` : raw;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString();
}
