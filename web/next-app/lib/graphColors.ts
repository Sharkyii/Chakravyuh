export function riskColor(risk: string): string {
  switch (risk) {
    case "critical":
    case "high":
      return "#ef4444";
    case "medium":
    case "warning":
      return "#f97316";
    case "low":
      return "#10b981";
    default:
      return "#27272a";
  }
}

export function edgeStatusColor(status: string): string {
  if (status === "critical" || status === "high") return "#ef4444";
  if (status === "medium" || status === "warning") return "#f97316";
  if (status === "linkage") return "#10b981";
  return "#27272a";
}
