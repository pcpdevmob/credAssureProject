// U5 scorecards: baseline vs system vs ablations, as the gateway reads them from `make eval` / `make baseline` runs.
import { gw, ok } from '@/lib/gateway';

export interface RunScore { label: string; passed: number; total: number; byCategory: Record<string, [number, number]>; detail: string }
export interface Scorecard { baseline: RunScore | null; full: RunScore | null; ablations: RunScore[] }
type Wire = { passed: number; total: number; by_category: Record<string, [number, number]>; run?: string; model?: string; strategy?: string } | null;

const run = (label: string, w: Wire): RunScore | null => w && ({ label, passed: w.passed, total: w.total, byCategory: w.by_category, detail: w.strategy ?? [w.model, w.run].filter(Boolean).join(' · ') });
export function mapScorecard(w: { baseline: Wire; full: Wire; ablations: Record<string, Wire> }): Scorecard {
  return { baseline: run('Best baseline', w.baseline), full: run('Full system', w.full),
    ablations: Object.entries(w.ablations).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => run(k, v)).filter((x): x is RunScore => x !== null) };
}
export const evaluationService = {
  async scorecard(): Promise<Scorecard> { return mapScorecard(await ok(gw.GET('/v1/eval/scorecard')) as never); },
};
