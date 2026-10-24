import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import App from './App.tsx'
import './index.css'
import Collector from './pages/Collector.tsx'
import Dashboard from './pages/Dashboard.tsx'
import Request from './pages/Request.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route index element={<Dashboard />} />
          <Route path="collector" element={<Collector />} />
          <Route path="request" element={<Request />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
