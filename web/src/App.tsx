import { NavLink, Outlet } from 'react-router-dom'

const tabs = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/collector', label: 'Collector · आवाज़' },
  { to: '/request', label: 'Request pickup' },
]

export default function App() {
  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-[1000] border-b border-line bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <div className="flex items-baseline gap-2">
            <span className="font-display text-xl font-bold">Kabaad Line</span>
            <span className="text-sm text-muted">कबाड़ लाइन · IIT Roorkee</span>
          </div>
          <nav className="flex gap-1 overflow-x-auto">
            {tabs.map((t) => (
              <NavLink key={t.to} to={t.to} end={t.end}
                className={({ isActive }) => `whitespace-nowrap rounded-full px-3 py-1.5 text-sm font-medium transition ${isActive ? 'bg-ink text-paper' : 'text-ink hover:bg-line'}`}>
                {t.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
