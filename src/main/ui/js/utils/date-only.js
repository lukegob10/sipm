export const DAY_MS = 24 * 60 * 60 * 1000;

export function parseDateOnly(value) {
  const raw = String(value || "").trim().slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return null;
  const [yearText, monthText, dayText] = raw.split("-");
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) return null;
  const time = Date.UTC(year, month - 1, day);
  const date = new Date(time);
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
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;
}

export function todayDayNumber() {
  const today = new Date();
  return Math.floor(Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()) / DAY_MS);
}

export function startOfDateOnlyDay(value) {
  if (value instanceof Date) {
    return new Date(Date.UTC(value.getFullYear(), value.getMonth(), value.getDate()));
  }
  return dateOnlyToDate(value);
}

export function daysBetweenDateOnly(fromDate, toDate) {
  return Math.ceil((toDate.getTime() - fromDate.getTime()) / DAY_MS);
}

