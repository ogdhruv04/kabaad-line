import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip } from 'react-leaflet'
import { fillColor, ROUTE_COLORS, type Loc, type Route } from '../api'

export default function CampusMap({ locations, routes }: { locations: Loc[]; routes: Route[] }) {
  const depot = locations.find((l) => l.kind === 'depot')
  if (!locations.length) return <div className="h-[340px] rounded-2xl bg-line/50 sm:h-[460px]" />
  const bounds = locations.map((l) => [l.lat, l.lng] as [number, number])
  return (
    <MapContainer bounds={bounds} boundsOptions={{ padding: [24, 24] }} className="h-[340px] sm:h-[460px]" scrollWheelZoom={false}>
      <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {routes.map((r, i) => depot && (
        <Polyline key={r.id} positions={[[depot.lat, depot.lng], ...r.stops.map((s) => [s.lat, s.lng] as [number, number]), [depot.lat, depot.lng]]}
          pathOptions={{ color: ROUTE_COLORS[i % ROUTE_COLORS.length], weight: 4, opacity: 0.85, dashArray: '1 7', lineCap: 'round' }} />
      ))}
      {locations.map((l) => (
        <CircleMarker key={l.id} center={[l.lat, l.lng]} radius={l.kind === 'depot' ? 11 : l.kind === 'hostel' ? 9 : 7}
          pathOptions={{ color: l.kind === 'depot' ? '#1f2a22' : '#fffdf8', weight: 2, fillColor: l.kind === 'depot' ? '#1f2a22' : fillColor(l.fill_pct), fillOpacity: 0.95 }}>
          <Tooltip>
            <b>{l.name}</b><br />
            {l.kind === 'depot' ? 'Depot / MRF' : `${l.fill_pct ?? '—'}% full · ${l.fill_source === 'sensor_sim' ? 'simulated sensor' : l.fill_source}`}
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}
