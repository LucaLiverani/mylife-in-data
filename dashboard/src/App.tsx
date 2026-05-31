import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import { RouteErrorBoundary } from '@/components/RouteErrorBoundary';
import { Nav } from '@/components/Nav';
import { Footer } from '@/components/Footer';

const Home    = lazy(() => import('./pages/Home'));
const Spotify = lazy(() => import('./pages/Spotify'));
const YouTube = lazy(() => import('./pages/YouTube'));
const Google  = lazy(() => import('./pages/Google'));
const Maps    = lazy(() => import('./pages/Maps'));
const Now     = lazy(() => import('./pages/Now'));
const System  = lazy(() => import('./pages/System'));

function PageFallback() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center text-signal-white">
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
          <Route path="/now"     element={<Now />} />
          <Route path="/system"  element={<System />} />
        </Routes>
      </Suspense>
    </RouteErrorBoundary>
  );
}

function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen flex-col">
        <Nav />
        <div className="flex-1">
          <AppRoutes />
        </div>
        <Footer />
      </div>
    </BrowserRouter>
  );
}

export default App;
