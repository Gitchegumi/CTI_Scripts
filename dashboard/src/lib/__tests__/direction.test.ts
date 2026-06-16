import { describe, it, expect } from "vitest";
import { isBullishDirection, directionColorClasses } from "@/lib/direction";

describe("direction helpers", () => {
  it("treats BUY/UPTREND/LONG/CALL as bullish", () => {
    expect(isBullishDirection("BUY")).toBe(true);
    expect(isBullishDirection("UPTREND")).toBe(true);
    expect(isBullishDirection("Long")).toBe(true);
    expect(isBullishDirection("call")).toBe(true);
  });

  it("treats SELL/DOWNTREND/SHORT and unknown as not bullish", () => {
    expect(isBullishDirection("SELL")).toBe(false);
    expect(isBullishDirection("DOWNTREND")).toBe(false);
    expect(isBullishDirection("SHORT")).toBe(false);
    expect(isBullishDirection("UNKNOWN")).toBe(false);
  });

  it("returns green classes for bullish directions", () => {
    expect(directionColorClasses("UPTREND")).toEqual({
      text: "text-green-400",
      bg: "bg-green-900/30",
      border: "border-green-700",
    });
  });

  it("returns red classes for bearish directions", () => {
    expect(directionColorClasses("DOWNTREND")).toEqual({
      text: "text-red-400",
      bg: "bg-red-900/30",
      border: "border-red-700",
    });
  });

  it("returns neutral/gray classes for unknown or empty directions", () => {
    for (const dir of ["", "NONE", "UNKNOWN", "NEUTRAL", "FLAT", undefined]) {
      expect(directionColorClasses(dir)).toEqual({
        text: "text-slate-400",
        bg: "bg-slate-800/30",
        border: "border-slate-700",
      });
    }
  });
});
