export const API = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? 'http://localhost:8000'

export async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`)
  if (!r.ok) throw new Error(`${r.status} ${path}`)
  return r.json()
}

export async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!r.ok) throw new Error(`${r.status} ${path}`)
  return r.json()
}

export type Loc = {
  id: number; name: string; kind: string; lat: number; lng: number; capacity_l: number
  fill_pct: number | null; fill_source: string | null; fill_ts: string | null
}
export type Stop = { location_id: number; name: string; lat: number; lng: number; est_kg: number; reasons: string[] }
export type Route = {
  id: number; collector_id: number; collector_name: string; stops: Stop[]; distance_km: number
  briefing_text: string; audio_url: string | null
}
export type Impact = { baseline_km: number; optimized_km: number; km_saved: number; pct_saved: number; fuel_l_saved: number; co2_kg_saved: number; stops: number; dropped: string[] }
export type Latest = { run: { id: number; plan_date: string; engine: string; workflow_run_id: string; impact: Impact | null } | null; routes: Route[] }
export type Kpis = {
  days: number; total_kg: number; recyclable_kg: number; diversion_pct: number; inr_recovered: number; co2e_avoided_kg: number
  mlp_share_pct: number; by_material: { material: string; label: string; kg: number; kg_real: number }[]
  bins_over_80: number; open_pickups: number; voice_reports_24h: number; routing: Impact | null; simulated_note: string
}
export type FeedItem = { type: 'report' | 'collection' | 'pickup'; kind: string; text: string; location: string; who: string; channel: string; simulated: boolean; ts: string }
export type Collector = { id: number; name: string; vehicle_capacity_kg: number }

export const ROUTE_COLORS = ['#2e7a4c', '#b9864a', '#3d6fb6', '#8a4fb0', '#c9482f']

export function fillColor(pct: number | null) {
  if (pct == null) return '#9aa196'
  if (pct >= 100) return '#c9482f'
  if (pct >= 75) return '#d99a2b'
  if (pct >= 40) return '#b9864a'
  return '#2e7a4c'
}

export function timeAgo(iso: string) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return `${Math.floor(s / 86400)} d ago`
}
