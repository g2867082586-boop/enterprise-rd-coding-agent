import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth";

export function ProtectedRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="screen-loader"><span className="spinner" />正在确认登录状态…</div>;
  return user ? <Outlet /> : <Navigate to="/login" replace state={{ from: location.pathname }} />;
}
