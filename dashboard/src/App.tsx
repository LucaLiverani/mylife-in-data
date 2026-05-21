import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import { RouteErrorBoundary } from '@/components/RouteErrorBoundary';

const Home    = lazy(() => import('./pages/Home'));
const Spotify = lazy(() => import('./pages/Spotify'));
const YouTube = lazy(() => import('./pages/YouTube'));
const Google  = lazy(() => import('./pages/Google'));
const Maps    = lazy(() => import('./pages/Maps'));

function PageFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-rack-black to-rack-charcoal text-signal-white">
      <p className="font-mono text-sm uppercase tracking-wider text-signal-white/60">Loading…</p>
    </div>
  );
}

function AppRoutes() {
  const location = useLocation();
  return (
    <RouteErrorBoundary resetKey={location.pathname}>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/"        element={<Home />} />
          <Route path="/spotify" element={<Spotify />} />
          <Route path="/youtube" element={<YouTube />} />
          <Route path="/google"  element={<Google />} />
          <Route path="/maps"    element={<Maps />} />
        </Routes>
      </Suspense>
    </RouteErrorBoundary>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}

export default App;
