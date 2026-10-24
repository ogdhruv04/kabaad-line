import { useCallback, useEffect, useState } from 'react'
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { get, post, ROUTE_COLORS, type FeedItem, type Kpis, type Latest, type Loc } from '../api'
import CampusMap from '../components/CampusMap'
import { Card, Feed, LiveBadge, SimBadge, Stat } from '../components/ui'

type RunStatus = { id: number; status: string; engine: string; workflow_run_id: string; summary: { error?: string } }

export default function Dashboard() {
  const [locs, setLocs] = useState<Loc[]>([])
  const [kpis, setKpis] = useState<Kpis | null>(null)
  const [latest, setLatest] = useState<Latest>({ run: null, routes: [] })
  const [feed, setFeed] = useState<FeedItem[]>([])
  const [moveOut, setMoveOut] = useState(false)
  const [run, setRun] = useState<RunStatus | null>(null)

  const refresh = useCallback(async () => {
    const [l, k, r, f] = await Promise.all([get<Loc[]>('/api/locations'), get<Kpis>('/api/kpis'), get<Latest>('/api/routes/latest'), get<FeedItem[]>('/api/feed?limit=12')])
    setLocs(l); setKpis(k); setLatest(r); setFeed(f)
  }, [])

  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t) }, [refresh])

  useEffect(() => {
    if (!run || run.status !== 'running') return
    const t = setInterval(async () => {
      const s = await get<RunStatus>(`/api/plan/runs/${run.id}`)
      setRun(s)
      if (s.status !== 'running') refresh()
    }, 1500)
    return () => clearInterval(t)
  }, [run, refresh])

  const plan = async () => {
    const r = await post<{ plan_run_id: number; engine: string; workflow_run_id: string }>('/api/plan/run', { move_out: moveOut })
    setRun({ id: r.plan_run_id, status: 'running', engine: r.engine, workflow_run_id: r.workflow_run_id, summary: {} })
  }

  const impact = latest.run?.impact

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">Campus waste, today</h1>
          <p className="text-muted">Collectors report by voice. Tomorrow's routes are planned from what they say.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={moveOut} onChange={(e) => setMoveOut(e.target.checked)} className="accent-leaf" />
            Semester move-out mode
          </label>
          <button onClick={plan} disabled={run?.status === 'running'}
            className="rounded-full bg-leaf px-5 py-2.5 font-semibold text-white shadow transition hover:brightness-110 disabled:opacity-60">
            {run?.status === 'running' ? 'Planning…' : 'Plan tomorrow'}
          </button>
        </div>
      </div>

      {run && (
        <Card className="text-sm">
          Plan run #{run.id} · <b>{run.status}</b> · engine: {run.engine === 'render_workflow' ? `Render Workflow (${run.workflow_run_id})` : 'local fallback'}
          {run.summary?.error && <span className="text-alert"> · {run.summary.error}</span>}
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Route km saved (tomorrow)" value={impact ? `${impact.pct_saved}%` : '—'}
          sub={impact ? `${impact.optimized_km} km vs ${impact.baseline_km} km fixed round` : 'Run “Plan tomorrow”'} />
        <Stat label={`Diverted from landfill (${kpis?.days ?? 7}d)`} value={kpis ? `${kpis.diversion_pct}%` : '—'} sub={kpis && `${kpis.recyclable_kg.toLocaleString()} kg recyclable`} badge={<SimBadge />} />
        <Stat label="Value recovered" value={kpis ? `₹${kpis.inr_recovered.toLocaleString('en-IN')}` : '—'} sub={kpis && `${kpis.co2e_avoided_kg.toLocaleString()} kg CO₂e avoided`} badge={<SimBadge />} />
        <Stat label="Voice reports (24h)" value={kpis?.voice_reports_24h ?? '—'} sub={kpis && `${kpis.bins_over_80} bins >80% · ${kpis.open_pickups} pickups open`} badge={<LiveBadge />} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-bold">Bins & tomorrow's routes</h2>
            <div className="flex flex-wrap gap-3 text-xs text-muted">
              {latest.routes.map((r, i) => (
                <span key={r.id} className="flex items-center gap-1"><span className="h-2 w-4 rounded" style={{ background: ROUTE_COLORS[i % ROUTE_COLORS.length] }} />{r.collector_name} · {r.stops.length} stops · {r.distance_km} km</span>
              ))}
            </div>
          </div>
          <CampusMap locations={locs} routes={latest.routes} />
          {impact?.dropped?.length ? <p className="mt-2 text-sm text-alert">Over vehicle capacity, needs an extra trip: {impact.dropped.join(', ')}</p> : null}
          <p className="mt-2 text-xs text-muted">Fill levels from the seed script are simulated; voice and student reports override them live. Map positions from OpenStreetMap; depot location approximate.</p>
        </Card>
        <Card>
          <div className="mb-2 flex items-center justify-between"><h2 className="text-lg font-bold">Live feed</h2><LiveBadge /></div>
          <Feed items={feed} />
        </Card>
      </div>

      <Card>
        <div className="mb-2 flex items-center justify-between"><h2 className="text-lg font-bold">Collected by material, last {kpis?.days ?? 7} days</h2><SimBadge /></div>
        <div style={{ height: 260 }}>
          <ResponsiveContainer>
            <BarChart data={kpis?.by_material ?? []} margin={{ left: 8 }}>
              <XAxis dataKey="label" tick={{ fontSize: 12 }} interval={0} />
              <YAxis tick={{ fontSize: 12 }} unit=" kg" width={70} />
              <Tooltip formatter={(v) => `${Number(v).toFixed(0)} kg`} />
              <Bar dataKey="kg" fill="#b9864a" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        {kpis && <p className="text-sm text-muted">Multilayer packaging (non-recyclable) is {kpis.mlp_share_pct}% of collected weight.</p>}
      </Card>
    </div>
  )
}
