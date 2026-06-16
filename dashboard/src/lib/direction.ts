export function isBullishDirection(direction: string | undefined): boolean {
  const d = (direction ?? "").toUpperCase();
  return d === "BUY" || d === "UPTREND" || d === "LONG" || d === "CALL";
}
export function directionColorClasses(direction: string | undefined): {
  text: string;
  bg: string;
  border: string;
} {
  const d = (direction ?? "").trim().toUpperCase();
  if (d === "" || d === "NONE" || d === "UNKNOWN" || d === "NEUTRAL" || d === "FLAT") {
    return {
      text: "text-slate-400",
      bg: "bg-slate-800/30",
      border: "border-slate-700",
    };
  }
  const bullish = isBullishDirection(direction);
  return {
    text: bullish ? "text-green-400" : "text-red-400",
    bg: bullish ? "bg-green-900/30" : "bg-red-900/30",
    border: bullish ? "border-green-700" : "border-red-700",
  };
}
