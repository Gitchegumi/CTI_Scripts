"use client";

import { useState, useEffect } from "react";
import { ApiStatus, setMode, setProgram, setPhase, triggerRescan } from "@/lib/api";

interface SettingsPanelProps {
  status: ApiStatus | null;
}

const MODES: { value: ApiStatus["mode"]; label: string }[] = [
  { value: "alert_only", label: "Alert Only" },
  { value: "demo", label: "Demo" },
  { value: "live", label: "Live ⚠️" },
];

const PROGRAMS: { value: ApiStatus["program"]; label: string }[] = [
  { value: "challenge", label: "Challenge" },
  { value: "instant", label: "Instant" },
];

const PHASES: { value: ApiStatus["phase"]; label: string }[] = [
  { value: 1, label: "Phase 1" },
  { value: 2, label: "Phase 2" },
  { value: 3, label: "Funded" },
];

function modeColor(mode: ApiStatus["mode"]): string {
  switch (mode) {
    case "alert_only": return "bg-blue-600 text-blue-100 ring-blue-500";
    case "demo": return "bg-yellow-600 text-yellow-100 ring-yellow-500";
    case "live": return "bg-red-600 text-red-100 ring-red-500";
  }
}

function programColor(program: ApiStatus["program"]): string {
  return program === "instant"
    ? "bg-emerald-600 text-emerald-100 ring-emerald-500"
    : "bg-slate-600 text-slate-100 ring-slate-500";
}

function phaseColor(phase: ApiStatus["phase"]): string {
  switch (phase) {
    case 1: return "bg-blue-600 text-blue-100 ring-blue-500";
    case 2: return "bg-yellow-600 text-yellow-100 ring-yellow-500";
    case 3: return "bg-green-600 text-green-100 ring-green-500";
  }
}

export default function SettingsPanel({ status }: SettingsPanelProps) {
  const [open, setOpen] = useState(false);
  const [rescanning, setRescanning] = useState(false);
  const [pendingMode, setPendingMode] = useState<ApiStatus["mode"] | null>(null);
  const [pendingProgram, setPendingProgram] = useState<ApiStatus["program"] | null>(null);
  const [pendingPhase, setPendingPhase] = useState<ApiStatus["phase"] | null>(null);

  const mode = status?.mode ?? pendingMode ?? "alert_only";
  const program = status?.program ?? pendingProgram ?? "challenge";
  const phase = status?.phase ?? pendingPhase ?? 1;

  // Sync pending state to live status once it arrives
  useEffect(() => {
    if (status) {
      setPendingMode(status.mode);
      setPendingProgram(status.program);
      setPendingPhase(status.phase);
    }
  }, [status]);

  async function handleMode(m: ApiStatus["mode"]) {
    try {
      await setMode(m);
      setPendingMode(m);
    } catch (e) {
      console.error("setMode failed", e);
    }
  }

  async function handleProgram(p: ApiStatus["program"]) {
    try {
      await setProgram(p);
      setPendingProgram(p);
    } catch (e) {
      console.error("setProgram failed", e);
    }
  }

  async function handlePhase(p: ApiStatus["phase"]) {
    try {
      await setPhase(p);
      setPendingPhase(p);
    } catch (e) {
      console.error("setPhase failed", e);
    }
  }

  async function handleRescan() {
    setRescanning(true);
    try {
      await triggerRescan();
    } catch (e) {
      console.error("triggerRescan failed", e);
    } finally {
      setTimeout(() => setRescanning(false), 3000);
    }
  }

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg overflow-hidden">
      {/* Panel header */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-semibold text-slate-300 hover:bg-slate-800 transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <span>⚙️</span>
          <span>Settings</span>
        </span>
        <span className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`}>
          ▾
        </span>
      </button>

      {/* Collapsible content */}
      <div
        className="overflow-hidden transition-all duration-300 ease-in-out"
        style={{ maxHeight: open ? "400px" : "0" }}
      >
        <div className="px-4 pb-4 space-y-4">
          {/* Mode */}
          <div className="space-y-1.5">
            <label className="text-xs text-slate-500 uppercase tracking-wide font-medium">
              Trading Mode
            </label>
            <div className="flex gap-2">
              {MODES.map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => handleMode(value)}
                  className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-full border transition-all duration-150
                    ${mode === value
                      ? `${modeColor(value)} ring-2 ring-offset-1 ring-offset-slate-900`
                      : "bg-slate-800 text-slate-400 border-slate-700 hover:bg-slate-700"
                    }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Program */}
          <div className="space-y-1.5">
            <label className="text-xs text-slate-500 uppercase tracking-wide font-medium">
              Program
            </label>
            <div className="flex gap-2">
              {PROGRAMS.map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => handleProgram(value)}
                  className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-full border transition-all duration-150
                    ${program === value
                      ? `${programColor(value)} ring-2 ring-offset-1 ring-offset-slate-900`
                      : "bg-slate-800 text-slate-400 border-slate-700 hover:bg-slate-700"
                    }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Phase — only shown for challenge program */}
          <div
            className="space-y-1.5 transition-all duration-300 ease-in-out"
            style={{ opacity: program === "challenge" ? 1 : 0, height: program === "challenge" ? "auto" : 0, overflow: "hidden" }}
          >
            <label className="text-xs text-slate-500 uppercase tracking-wide font-medium">
              Phase
            </label>
            <div className="flex gap-2">
              {PHASES.map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => handlePhase(value)}
                  className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-full border transition-all duration-150
                    ${phase === value
                      ? `${phaseColor(value)} ring-2 ring-offset-1 ring-offset-slate-900`
                      : "bg-slate-800 text-slate-400 border-slate-700 hover:bg-slate-700"
                    }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Re-scan */}
          <div className="pt-1">
            <button
              onClick={handleRescan}
              disabled={rescanning}
              className="flex items-center justify-center gap-2 w-full px-3 py-2 text-xs font-medium rounded border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <span className={rescanning ? "animate-spin" : ""}>🔄</span>
              {rescanning ? "Rescanning..." : "Re-scan Watchlist"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}