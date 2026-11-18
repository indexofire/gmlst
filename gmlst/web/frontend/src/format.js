/**
 * Number formatting shared by the workspace and its analysis views.
 * Returns an en dash for empty values; keeps non-numeric strings as-is.
 */
export function formatNumber(value) {
  if (value === null || value === undefined || value === "") {
    return "–";
  }
  const num = Number(value);
  return Number.isFinite(num) ? num.toLocaleString() : String(value);
}
