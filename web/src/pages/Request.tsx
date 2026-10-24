import { useEffect, useState, type FormEvent } from 'react'
import { get, post, timeAgo, type Loc, type Pickup } from '../api'
import { Card } from '../components/ui'

const T = {
  en: { title: 'Got scrap? We’ll pick it up.', sub: 'Cartons, bottles, old electronics — especially during move-out. It goes to a collector’s route tomorrow.', where: 'Where', what: 'What', kg: 'Roughly how many kg?', contact: 'Room / phone (optional)', note: 'Anything else', send: 'Request pickup', done: 'Done! It will be on tomorrow’s route.', report: 'Or report an overflowing bin here', reportBtn: 'Report overflow', recent: 'Recent requests', status: { pending: 'requested', scheduled: 'on tomorrow’s route', collected: 'collected ✓' } },
  hi: { title: 'कबाड़ है? हम उठा लेंगे।', sub: 'गत्ते, बोतलें, पुराने इलेक्ट्रॉनिक्स — ख़ासकर हॉस्टल खाली करते समय। यह कल के रूट में जुड़ जाएगा।', where: 'कहाँ', what: 'क्या', kg: 'लगभग कितने किलो?', contact: 'कमरा / फ़ोन (वैकल्पिक)', note: 'और कुछ', send: 'पिकअप बुलाएँ', done: 'हो गया! यह कल के रूट में है।', report: 'या यहाँ भरे हुए डस्टबिन की शिकायत करें', reportBtn: 'शिकायत करें', recent: 'हाल के अनुरोध', status: { pending: 'अनुरोध मिला', scheduled: 'कल के रूट में', collected: 'उठा लिया ✓' } },
}
const MATS = [['cardboard', 'Cardboard / paper · गत्ता'], ['pet', 'PET bottles · बोतल'], ['metal', 'Metal / cans · लोहा'], ['ewaste', 'E-waste · ई-कचरा'], ['hdpe', 'Hard plastic · प्लास्टिक'], ['glass', 'Glass · काँच']]

export default function Request() {
  const [lang, setLang] = useState<'en' | 'hi'>('en')
  const [locs, setLocs] = useState<Loc[]>([])
  const [form, setForm] = useState({ location_id: 0, material: 'cardboard', est_kg: 5, contact: '', note: '' })
  const [msg, setMsg] = useState('')
  const [pickups, setPickups] = useState<Pickup[]>([])
  const t = T[lang]

  useEffect(() => { get<Loc[]>('/api/locations').then((l) => { const ok = l.filter((x) => x.kind !== 'depot'); setLocs(ok); setForm((f) => ({ ...f, location_id: ok[0]?.id ?? 0 })) }) }, [])

  useEffect(() => {
    const load = () => get<Pickup[]>('/api/pickups?limit=6').then(setPickups)
    load(); const id = setInterval(load, 5000); return () => clearInterval(id)
  }, [])

  const submit = async (e: FormEvent) => { e.preventDefault(); await post('/api/pickups', form); setMsg(t.done); setPickups(await get<Pickup[]>('/api/pickups?limit=6')) }
  const report = async () => { await post('/api/reports', { location_id: form.location_id, kind: 'overflow', text: form.note }); setMsg(t.done) }

  const field = 'mt-1 w-full rounded-xl border border-line bg-paper px-3 py-2.5'
  return (
    <div className="mx-auto max-w-xl">
      <Card>
        <div className="flex items-start justify-between gap-3">
          <h1 className="text-3xl font-bold">{t.title}</h1>
          <button onClick={() => setLang(lang === 'en' ? 'hi' : 'en')} className="rounded-full bg-line px-3 py-1 text-sm font-semibold">{lang === 'en' ? 'हिंदी' : 'English'}</button>
        </div>
        <p className="mt-1 text-muted">{t.sub}</p>
        <form onSubmit={submit} className="mt-5 grid gap-4">
          <label className="text-sm font-medium">{t.where}
            <select className={field} value={form.location_id} onChange={(e) => setForm({ ...form, location_id: +e.target.value })}>
              {locs.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium">{t.what}
            <select className={field} value={form.material} onChange={(e) => setForm({ ...form, material: e.target.value })}>
              {MATS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium">{t.kg}
            <input type="number" min={1} max={500} className={field} value={form.est_kg} onChange={(e) => setForm({ ...form, est_kg: +e.target.value })} />
          </label>
          <label className="text-sm font-medium">{t.contact}
            <input className={field} value={form.contact} onChange={(e) => setForm({ ...form, contact: e.target.value })} />
          </label>
          <label className="text-sm font-medium">{t.note}
            <textarea className={field} rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
          </label>
          <button className="rounded-full bg-leaf px-5 py-3 font-semibold text-white">{t.send}</button>
          <button type="button" onClick={report} className="text-sm text-alert underline">{t.report} → {t.reportBtn}</button>
          {msg && <p className="rounded-xl bg-leaf-soft p-3 text-sm text-leaf">{msg}</p>}
        </form>
      </Card>
      {pickups.length > 0 && (
        <Card className="mt-4">
          <h2 className="font-bold">{t.recent}</h2>
          <ul className="mt-2 divide-y divide-line">
            {pickups.map((p) => (
              <li key={p.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span><b>{p.location}</b> · ~{p.est_kg} kg {p.material} <span className="text-muted">· {timeAgo(p.ts)}</span></span>
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${
                  p.status === 'collected' ? 'bg-leaf-soft text-leaf' : p.status === 'scheduled' ? 'bg-amber/15 text-amber' : 'bg-line text-muted'}`}>{t.status[p.status]}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
