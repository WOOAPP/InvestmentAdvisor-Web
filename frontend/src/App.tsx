import { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/authStore';
import Layout from './components/Layout';
import Login from './pages/Login';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Portfolio = lazy(() => import('./pages/Portfolio'));
const Calendar = lazy(() => import('./pages/Calendar'));
const Charts = lazy(() => import('./pages/Charts'));
const History = lazy(() => import('./pages/History'));
const Settings = lazy(() => import('./pages/Settings'));
const Admin = lazy(() => import('./pages/Admin'));

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuthStore();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-[var(--overlay)]">Ladowanie...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const { fetchUser } = useAuthStore();

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<Suspense fallback={null}><Dashboard /></Suspense>} />
          <Route path="/portfolio" element={<Suspense fallback={null}><Portfolio /></Suspense>} />
          <Route path="/calendar" element={<Suspense fallback={null}><Calendar /></Suspense>} />
          <Route path="/charts" element={<Suspense fallback={null}><Charts /></Suspense>} />
          <Route path="/history" element={<Suspense fallback={null}><History /></Suspense>} />
          <Route path="/settings" element={<Suspense fallback={null}><Settings /></Suspense>} />
          <Route path="/admin" element={<Suspense fallback={null}><Admin /></Suspense>} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
