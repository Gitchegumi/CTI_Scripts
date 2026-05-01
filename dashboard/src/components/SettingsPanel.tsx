"use client";

import { useState, useEffect } from "react";
import { ApiStatus, setMode, setChallengeType, setPhase, triggerRescan } from "@/lib/api";

interface SettingsPanelProps {
  status: ApiStatus | null;
}

const MODES: { value: ApiStatus["mode"]; label: string }[] = [
  { value: "alert_only", label: "Alert Only" },
  { value: "demo", label: "Demo" },
  { value: "live", label: "Live ⚠️" },
];

const CHALLENGE_TYPES: { value: ApiStatus["challenge_type"]; label: string }[] = [
  { value: "1-step", label: "1-Step" },
  { value: "2-step", label: "2-Step" },
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

function challengeTypeColor(challenge_type: ApiStatus["challenge_type"]): string {
  return challenge_type === "instant"
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
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [pendingMode, setPendingMode] = useState<ApiStatus["mode"] | null>(null);
  const [pendingChallengeType, setPendingChallengeType] = useState<ApiStatus["challenge_type"] | null>(null);
  const [pendingPhase, setPendingPhase] = useState<ApiStatus["phase"] | null>(null);

  const mode = status?.mode ?? pendingMode ?? "alert_only";
  const challenge_type = status?.challenge_type ?? pendingChallengeType ?? "1-step";
  const phase = status?.phase ?? pendingPhase ?? 1;

  useEffect(() => {
    if (status) {
      const id = window.setTimeout(() => {
        setPendingMode(status.mode);
        setPendingChallengeType(status.challenge_type);
        setPendingPhase(status.phase);
      }, 0);
      return () => window.clearTimeout(id);
    }
  }, [status]);

  useEffect(() => {
    fetch("/api/auth-check").then(async (r) => {
      if (r.ok) {
        const data = await r.json();
        setAuthed(data.authed);
      } else {
        setAuthed(false);
      }
    });
  }, []);

  async function handleMode(m: ApiStatus["mode"]) {
    try {
      await setMode(m);
      setPendingMode(m);
    } catch (e) {
      console.error("setMode failed", e);
    }
  }

  async function handleChallengeType(ct: ApiStatus["challenge_type"]) {
    try {
      await setChallengeType(ct);
      setPendingChallengeType(ct);
    } catch (e) {
      console.error("setChallengeType failed", e);
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
        className="overflow-hidden transition-all duration-300 ease-in-out relative"
        style={{ maxHeight: open ? "400px" : "0" }}
      >
        <div className="px-4 pb-4 space-y-4">
          {/* Mode */}
          <div className="space-y-1.5">
            <label className="text-xs text-slate-500 uppercase tracking-wide font-medium">
              Trading Mode
            </label>
            <div className="flex gap-2 relative">
              {MODES.map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => authed ? handleMode(value) : undefined}
                  disabled={!authed}
                  className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-full border transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed
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

          {/* Challenge Type */}
          <div className="space-y-1.5">
            <label className="text-xs text-slate-500 uppercase tracking-wide font-medium">
              Challenge Type
            </label>
            <div className="flex gap-2">
              {CHALLENGE_TYPES.map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => authed ? handleChallengeType(value) : undefined}
                  disabled={!authed}
                  className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-full border transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed
                    ${challenge_type === value
                      ? `${challengeTypeColor(value)} ring-2 ring-offset-1 ring-offset-slate-900`
                      : "bg-slate-800 text-slate-400 border-slate-700 hover:bg-slate-700"
                    }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Phase — only shown for 1-step and 2-step challenge types */}
          {(challenge_type === "1-step" || challenge_type === "2-step") && (
            <div className="space-y-1.5">
              <label className="text-xs text-slate-500 uppercase tracking-wide font-medium">
                Phase
              </label>
              <div className="flex gap-2">
                {PHASES.map(({ value, label }) => (
                  <button
                    key={value}
                    onClick={() => authed ? handlePhase(value) : undefined}
                    disabled={!authed}
                    className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-full border transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed
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
          )}

          {/* Funded badge for instant challenge type */}
          {challenge_type === "instant" && (
            <div className="space-y-1.5">
              <label className="text-xs text-slate-500 uppercase tracking-wide font-medium">
                Status
              </label>
              <div className="flex gap-2">
                <span className="flex-1 px-3 py-1.5 text-xs font-medium rounded-full bg-emerald-600 text-emerald-100 ring-2 ring-emerald-500 ring-offset-1 ring-offset-slate-900">
                  Funded
                </span>
              </div>
            </div>
          )}

          {/* Re-scan */}
          <div className="pt-1">
            <button
              onClick={handleRescan}
              disabled={rescanning || !authed}
              className="flex items-center justify-center gap-2 w-full px-3 py-2 text-xs font-medium rounded border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <span className={rescanning ? "animate-spin" : ""}>🔄</span>
              {rescanning ? "Rescanning..." : "Re-scan Watchlist"}
            </button>
          </div>
        </div>
        {/* Auth overlay */}
        {authed === false && (
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center rounded-lg">
            <div className="text-center px-4">
              <div className="text-2xl mb-2">🔒</div>
              <div className="text-sm font-medium text-slate-300">Settings Locked</div>
              <a href="/journal/login" className="text-xs text-blue-400 hover:text-blue-300 mt-1 inline-block">
                Log in to Journal →
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
