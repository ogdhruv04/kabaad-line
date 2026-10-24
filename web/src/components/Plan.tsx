import type { Impact, Kpis, RunStatus } from '../api'
import { Card, SimBadge } from './ui'

const STEP_LABELS: Record<string, string> = {
  load_state: 'Load state',
  forecast_fill: 'Forecast fill',
  select_stops: 'Select stops',
  solve_routes: 'Solve VRP',
  publish_routes: 'Publish routes',
  synthesize_briefing: 'Hindi TTS × collectors',
}

/** The planning pipeline, one chip per Render Workflow task, lit up as each step reports back. */
export function PipelineSteps({ run }: { run: RunStatus }) {
  const done = new Set(run.steps)
  const current = run.status === 'running' ? run.all_steps.find((s) => !done.has(s)) : undefined
  const onRender = run.engine === 'render_workflow'
  return (
    <Card className="text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-semibold">
          Plan run #{run.id} · <span className={run.status === 'failed' ? 'text-alert' : run.status === 'done' ? 'text-leaf' : ''}>{run.status}</span>
        </div>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${onRender ? 'bg-ink text-paper' : 'bg-line text-ink'}`}>
          engine: {onRender ? 'Render Workflow' : 'in-process'}
        </span>
      </div>
      <ol className="mt-3 flex flex-wrap items-center gap-1.5">
        {run.all_steps.map((s, i) => {
          const state = done.has(s) ? 'done' : s === current ? 'current' : 'todo'
          return (
            <li key={s} className="flex items-center gap-1.5">
              {i > 0 && <span className={`hidden h-px w-3 sm:block ${state === 'todo' ? 'bg-line' : 'bg-leaf'}`} />}
              <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
                state === 'done' ? 'bg-leaf-soft text-leaf' : state === 'current' ? 'animate-pulse bg-amber/15 text-amber' : 'bg-line/60 text-muted'}`}>
                {state === 'done' ? '✓' : state === 'current' ? '●' : '○'} {STEP_LABELS[s] ?? s}
              </span>
            </li>
          )
        })}
      </ol>
      {onRender && run.workflow_run_id && <p className="mt-2 text-xs text-muted">Task run <code>{run.workflow_run_id}</code> — each chip is its own task in the Render dashboard; TTS fans out in parallel.</p>}
      {run.summary?.error && <p className="mt-2 text-alert">{run.summary.error}</p>}
    </Card>
  )
}

const fmt = (n: number) => Math.round(n).toLocaleString('en-IN')

/** One plain-language sentence a judge (or a hostel warden) can repeat. */
export function ImpactStory({ kpis, impact }: { kpis: Kpis; impact: Impact | null | undefined }) {
  return (
    <Card className="border-leaf/30 bg-leaf-soft/40">
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs font-semibold uppercase tracking-wide text-leaf">Impact this week</div>
        <SimBadge />
      </div>
      <p className="mt-2 font-display text-xl leading-snug sm:text-2xl">
        <b>{fmt(kpis.recyclable_kg)} kg</b> of recyclables kept out of landfill, worth <b>₹{fmt(kpis.inr_recovered)}</b> to collectors
        and <b>{(kpis.co2e_avoided_kg / 1000).toFixed(1)} t CO₂e</b> avoided.
        {impact && impact.pct_saved > 0 && <> Tomorrow's routes are <b>{impact.pct_saved}% shorter</b> than the fixed every-bin round.</>}
      </p>
      <p className="mt-2 text-sm text-muted">
        {kpis.mlp_share_pct}% of collected weight is multilayer packaging that no kabadiwala buys — the next thing to design out.
        Weights before today are simulated; route savings are computed live.
      </p>
    </Card>
  )
}
