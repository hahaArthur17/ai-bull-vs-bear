const marketDateFormatter = new Intl.DateTimeFormat("en-US", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

const chartDateFormatter = new Intl.DateTimeFormat("en-US", {
  day: "numeric",
  month: "short",
  timeZone: "UTC",
});

const quoteTimeFormatter = new Intl.DateTimeFormat("en-US", {
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  month: "short",
  timeZone: "UTC",
  timeZoneName: "short",
});

function parseDate(value: string | null | undefined): Date | null {
  const text = value?.trim();
  if (!text) return null;
  // Market-close and macro observations use YYYY-MM-DD, while evidence and
  // analysis timestamps use complete ISO 8601 values. Append a time only to
  // the former; doing it to an existing timestamp creates an invalid date.
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(text) ? `${text}T12:00:00Z` : text;
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatMarketDate(value: string | null | undefined): string {
  const date = parseDate(value);
  return date ? marketDateFormatter.format(date) : "Date unavailable";
}

export function formatChartDate(value: string | null | undefined): string {
  const date = parseDate(value);
  return date ? chartDateFormatter.format(date) : "—";
}

export function formatQuoteTime(value: string | null | undefined): string {
  const date = parseDate(value);
  return date ? quoteTimeFormatter.format(date) : "Time unavailable";
}
