import { useEffect, useState } from 'react'
import { get, type Collector as C, type FeedItem, type Latest } from '../api'
import { Card, Feed, LiveBadge } from '../components/ui'
import VoicePanel from '../components/VoicePanel'

const TRY_SAYING = [
  'राजेंद्र भवन के पीछे वाला डस्टबिन भर गया है',
  'Cautley se 12 kilo gatta uthaya',
  'Mera kal ka route batao',
  'Main gate market pe kooda bahar gir raha hai',
  'Raj bhawan ka dibba aadha bhara hai  (agent asks: Rajendra ya Rajiv?)',
]

export default function Collector() {
  const [collectors, setCollectors] = useState<C[]>([])
  const [who, setWho] = useState('Ramesh')
  const [latest, setLatest] = useState<Latest>({ run: null, routes: [] })
  const [feed, setFeed] = useState<FeedItem[]>([])

  useEffect(() => { get<C[]>('/api/collectors').then(setCollectors) }, [])
  useEffect(() => {
    const load = () => { get<Latest>('/api/routes/latest').then(setLatest); get<FeedItem[]>('/api/feed?limit=10').then((f) => setFeed(f.filter((i) => !i.simulated))) }
    load(); const t = setInterval(load, 3000); return () => clearInterval(t)
  }, [])

  const route = latest.routes.find((r) => r.collector_name === who)

  return (
    <div className="grid gap-4 lg:grid-cols-5">
      <div className="grid gap-4 lg:col-span-3">
        <Card>
          <h1 className="text-2xl font-bold sm:text-3xl">बोलिए, हम लिख लेंगे</h1>
          <p className="mt-1 text-muted">Speak, we'll log it. Collectors report full bins and what they picked up, in Hindi, without reading or typing anything.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {collectors.map((c) => (
              <button key={c.id} onClick={() => setWho(c.name)}
                className={`rounded-full px-4 py-2 text-sm font-semibold ${who === c.name ? 'bg-ink text-paper' : 'bg-line'}`}>{c.name}</button>
            ))}
          </div>
          <div className="mt-5 rounded-2xl border border-dashed border-kraft/60 bg-paper/50 p-4">
            <VoicePanel collectorName={who} />
          </div>
          <div className="mt-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted">Try saying</div>
            <ul className="mt-2 grid gap-2 sm:grid-cols-2">
              {TRY_SAYING.map((t) => <li key={t} className="rounded-xl bg-paper px-3 py-2 text-sm">“{t}”</li>)}
            </ul>
          </div>
        </Card>

        <Card>
          <h2 className="text-lg font-bold">{who} का कल का रूट</h2>
          {!route ? <p className="text-sm text-muted">No route yet. Press “Plan tomorrow” on the dashboard.</p> : (
            <>
              <p className="text-sm text-muted">{route.stops.length} stops · {route.distance_km} km · plan for {latest.run?.plan_date}</p>
              {route.audio_url
                ? <audio controls src={route.audio_url} className="mt-3 w-full" />
                : <p className="mt-3 rounded-xl bg-amber/10 p-3 text-sm">Audio briefing appears here once ElevenLabs TTS is configured.</p>}
              <ol className="mt-3 grid gap-2">
                {route.stops.map((s, i) => (
                  <li key={`${s.location_id}-${i}`} className="flex gap-3 rounded-xl bg-paper px-3 py-2">
                    <span className="font-display text-lg font-bold text-kraft">{i + 1}</span>
                    <div><div className="font-semibold">{s.name}</div><div className="text-xs text-muted">{s.reasons.join(' · ')} · ~{s.est_kg} kg</div></div>
                  </li>
                ))}
              </ol>
              <details className="mt-3 text-sm"><summary className="cursor-pointer text-muted">Briefing script</summary><p className="mt-2">{route.briefing_text}</p></details>
            </>
          )}
        </Card>
      </div>

      <Card className="lg:col-span-2">
        <div className="mb-2 flex items-center justify-between"><h2 className="text-lg font-bold">What the agent logged</h2><LiveBadge /></div>
        <Feed items={feed} />
      </Card>
    </div>
  )
}
