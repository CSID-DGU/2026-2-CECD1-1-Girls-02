export function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("ko-KR");
}

export const formatPercent = (value) => (value === null || value === undefined ? "-" : `${Math.round(value * 1000) / 10}%`);
export const formatNumber = (value, unit = "") => (value === null || value === undefined ? "-" : `${value.toLocaleString("ko-KR")}${unit}`);
