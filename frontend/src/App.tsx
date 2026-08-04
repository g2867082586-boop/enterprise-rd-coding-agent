import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ConfigProvider } from "antd";
import { lazy, Suspense } from "react";
import { AuthProvider } from "./auth";
import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";

const ChatPage = lazy(() => import("./pages/ChatPage").then(module => ({ default: module.ChatPage })));
const DashboardPage = lazy(() => import("./pages/DashboardPage").then(module => ({ default: module.DashboardPage })));
const LoginPage = lazy(() => import("./pages/LoginPage").then(module => ({ default: module.LoginPage })));
const ProfilePage = lazy(() => import("./pages/ProfilePage").then(module => ({ default: module.ProfilePage })));
const RegisterPage = lazy(() => import("./pages/RegisterPage").then(module => ({ default: module.RegisterPage })));
const TracePage = lazy(() => import("./pages/TracePage").then(module => ({ default: module.TracePage })));
const KnowledgeAdminPage = lazy(() => import("./pages/KnowledgeAdminPage").then(module => ({ default: module.KnowledgeAdminPage })));
const ApprovalsPage = lazy(() => import("./pages/ApprovalsPage").then(module => ({ default: module.ApprovalsPage })));
const ObservabilityPage = lazy(() => import("./pages/ObservabilityPage").then(module => ({ default: module.ObservabilityPage })));
const OrdersPage = lazy(() => import("./pages/OrdersPage").then(module => ({ default: module.OrdersPage })));

export default function App() {
  return <ConfigProvider theme={{ token: { colorPrimary: "#246bfd", borderRadius: 9 } }}><BrowserRouter><AuthProvider><Suspense fallback={<div className="screen-loader"><span className="spinner" />正在载入页面…</div>}><Routes>
    <Route path="/login" element={<LoginPage />} /><Route path="/register" element={<RegisterPage />} />
    <Route element={<ProtectedRoute />}><Route element={<AppLayout />}><Route index element={<DashboardPage />} /><Route path="chat" element={<ChatPage />} /><Route path="orders" element={<OrdersPage />} /><Route path="profile" element={<ProfilePage />} /><Route path="traces" element={<TracePage />} /><Route path="knowledge-admin" element={<KnowledgeAdminPage />} /><Route path="approvals" element={<ApprovalsPage />} /><Route path="observability" element={<ObservabilityPage />} /></Route></Route>
  </Routes></Suspense></AuthProvider></BrowserRouter></ConfigProvider>;
}
