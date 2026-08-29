export function riskColor(risk: string): string {
  switch (risk?.toLowerCase()) {
    case "critical":
    case "high":
      return "#E5484D";
    case "medium":
    case "warning":
      return "#D9A420";
    case "low":
      return "#3FBF7F";
    default:
      return "#232326";
  }
}

export function edgeStatusColor(status: string): string {
  const s = status?.toLowerCase();
  if (s === "critical" || s === "high") return "#E5484D";
  if (s === "medium" || s === "warning") return "#D9A420";
  if (s === "linkage") return "#3FBF7F";
  return "#232326";
}
