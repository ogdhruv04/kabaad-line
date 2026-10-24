import { useState } from 'react'
import { ConversationProvider, useConversation } from '@elevenlabs/react'

const AGENT_ID = import.meta.env.VITE_ELEVENLABS_AGENT_ID as string | undefined

type Line = { id: string; role: 'user' | 'agent' | 'tool'; text: string; error?: boolean }

const TOOL_LABEL: Record<string, string> = {
  report_bin_status: 'Bin status logged',
  log_collection: 'Collection logged',
  get_my_route: 'Route fetched',
}

function WaveBars({ active }: { active: boolean }) {
  return (
    <div className="flex h-8 items-center gap-1" aria-hidden>
      {[0, 1, 2, 3, 4].map((i) => (
        <span key={i} className={`block h-8 w-1.5 rounded-full bg-leaf ${active ? 'wave-bar' : 'scale-y-[0.25]'}`}
          style={{ animationDelay: `${i * 0.12}s` }} />
      ))}
    </div>
  )
}

function Voice({ collectorName }: { collectorName: string }) {
  const [lines, setLines] = useState<Line[]>([])
  const [err, setErr] = useState('')
  const upsert = (line: Line) => setLines((ls) => [...ls.filter((l) => l.id !== line.id), line].slice(-12))
  const conv = useConversation({
    onMessage: (m) => upsert({ id: `${m.role}-${m.response_id ?? m.event_id}`, role: m.role, text: m.message }),
    onAgentToolResponse: (t) => upsert({ id: `tool-${t.tool_call_id}`, role: 'tool', text: TOOL_LABEL[t.tool_name] ?? t.tool_name, error: t.is_error }),
    onError: (message) => setErr(String(message)),
  })
  const live = conv.status === 'connected'
  const connecting = conv.status === 'connecting'

  const start = async () => {
    setErr(''); setLines([])
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setErr('Microphone permission is needed to talk to the agent.')
      return
    }
    conv.startSession({ connectionType: 'webrtc', dynamicVariables: { collector_name: collectorName } })
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-col items-center gap-3 py-2 sm:flex-row sm:gap-5">
        <div className="relative grid h-28 w-28 shrink-0 place-items-center">
          {live && <><span className="ripple absolute inset-0 rounded-full bg-leaf/30" /><span className="ripple absolute inset-0 rounded-full bg-leaf/20" style={{ animationDelay: '1.1s' }} /></>}
          <button onClick={live ? conv.endSession : start} disabled={connecting}
            aria-label={live ? 'End call' : 'Start talking'}
            className={`relative grid h-24 w-24 place-items-center rounded-full text-white shadow-lg transition active:scale-95 disabled:opacity-60 ${live ? 'bg-alert' : 'bg-leaf hover:brightness-110'}`}>
            {live
              ? <svg viewBox="0 0 24 24" className="h-9 w-9" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
              : <svg viewBox="0 0 24 24" className="h-10 w-10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>}
          </button>
        </div>
        <div className="text-center sm:text-left">
          <div className="font-display text-xl font-bold">
            {connecting ? 'जुड़ रहे हैं…' : live ? (conv.isSpeaking ? 'एजेंट बोल रहा है…' : 'बोलिए, सुन रहे हैं…') : 'माइक दबाइए और बोलिए'}
          </div>
          <div className="text-sm text-muted">
            {live ? `Talking as ${collectorName} · tap the red button to hang up` : `Tap the mic and speak Hindi or Hinglish as ${collectorName}`}
          </div>
          <div className="mt-2 flex justify-center sm:justify-start"><WaveBars active={live && conv.isSpeaking} /></div>
        </div>
      </div>

      {err && <p className="rounded-xl bg-alert/10 p-3 text-sm text-alert">{err}</p>}

      {lines.length > 0 && (
        <ul className="grid max-h-72 gap-2 overflow-y-auto rounded-2xl bg-paper p-3" aria-live="polite">
          {lines.map((l) => l.role === 'tool' ? (
            <li key={l.id} className="flash-in mx-auto rounded-full bg-leaf-soft px-3 py-1 text-xs font-semibold text-leaf">
              {l.error ? '⚠️' : '✓'} {l.text} → dashboard
            </li>
          ) : (
            <li key={l.id} className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${l.role === 'user' ? 'ml-auto bg-kraft/15' : 'bg-card'}`}>
              <div className="text-[10px] font-semibold uppercase tracking-wide text-muted">{l.role === 'user' ? collectorName : 'Kabaad Line'}</div>
              {l.text}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Inline voice agent (ElevenLabs Agents over WebRTC) with a live transcript and tool-call receipts. */
export default function VoicePanel({ collectorName }: { collectorName: string }) {
  if (!AGENT_ID) {
    return <p className="rounded-xl bg-amber/10 p-3 text-sm">Set <code>VITE_ELEVENLABS_AGENT_ID</code> in <code>web/.env</code> to load the voice agent.</p>
  }
  return (
    <ConversationProvider key={collectorName} agentId={AGENT_ID}>
      <Voice collectorName={collectorName} />
    </ConversationProvider>
  )
}
