"use client";

import type { SearchMode } from "@/lib/contracts";
import { formatNumber } from "@/lib/i18n/format";
import { useLocale } from "@/lib/i18n/LocaleProvider";
import type { Hyperparameters } from "./types";

const MODES: readonly SearchMode[] = ["hybrid", "dense", "sparse"];

/** Live hyperparameters sent with every agent turn (`AgentChatRequest`). */
export function HyperparameterPanel({
  value,
  onChange,
  disabled,
}: {
  value: Hyperparameters;
  onChange: (next: Hyperparameters) => void;
  disabled?: boolean;
}) {
  const { locale, t } = useLocale();
  const set = <K extends keyof Hyperparameters>(key: K, v: Hyperparameters[K]) => onChange({ ...value, [key]: v });
  return (
    <fieldset className="card stack" disabled={disabled} style={{ margin: 0 }}>
      <legend className="sr-only">{t.agent.params.legend}</legend>
      <h2>{t.agent.params.title}</h2>
      <fieldset className="field segmented-field">
        <legend className="label">search_mode</legend>
        {/* Native radios: arrow keys, a single tab stop and screen-reader semantics come for free. */}
        <div className="segmented">
          {MODES.map((mode) => (
            <label key={mode} className="segment">
              <input type="radio" name="search_mode" value={mode} checked={value.search_mode === mode} onChange={() => set("search_mode", mode)} />
              <span>{t.agent.params.modes[mode]}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="field">
        <label htmlFor="hp-topk">
          top_k: <strong>{value.top_k}</strong>
        </label>
        <input id="hp-topk" type="range" min={1} max={20} value={value.top_k} onChange={(e) => set("top_k", Number(e.target.value))} />
      </div>
      <label className="row" htmlFor="hp-rerank" style={{ fontSize: "var(--text-sm)", fontWeight: 600 }}>
        <input id="hp-rerank" type="checkbox" checked={value.enable_rerank} onChange={(e) => set("enable_rerank", e.target.checked)} />
        enable_rerank
      </label>
      <div className="field">
        <label htmlFor="hp-temp">
          temperature: <strong>{formatNumber(locale, value.temperature, 1)}</strong>
        </label>
        <input
          id="hp-temp"
          type="range"
          min={0}
          max={2}
          step={0.1}
          value={value.temperature}
          onChange={(e) => set("temperature", Number(e.target.value))}
        />
      </div>
      <div className="field">
        <label htmlFor="hp-turns">
          max_turns: <strong>{value.max_turns}</strong>
        </label>
        <input id="hp-turns" type="range" min={1} max={10} value={value.max_turns} onChange={(e) => set("max_turns", Number(e.target.value))} />
      </div>
      <p className="subtle" style={{ margin: 0 }}>
        {t.agent.params.note}
      </p>
    </fieldset>
  );
}
