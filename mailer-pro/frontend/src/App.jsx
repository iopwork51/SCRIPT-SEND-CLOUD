import { Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Accounts from "./pages/Accounts";
import Groups from "./pages/Groups";
import Recipients from "./pages/Recipients";
import Affiliates from "./pages/Affiliates";
import Offers from "./pages/Offers";
import Campaigns from "./pages/Campaigns";
import Send from "./pages/Send";
import Blacklist from "./pages/Blacklist";
import Stats from "./pages/Stats";
import Proxies from "./pages/Proxies";

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center h-screen text-gray-500">Loading…</div>;
  return user ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="accounts" element={<Accounts />} />
          <Route path="groups" element={<Groups />} />
          <Route path="recipients" element={<Recipients />} />
          <Route path="affiliates" element={<Affiliates />} />
          <Route path="offers" element={<Offers />} />
          <Route path="campaigns" element={<Campaigns />} />
          <Route path="send" element={<Send />} />
          <Route path="blacklist" element={<Blacklist />} />
          <Route path="stats" element={<Stats />} />
          <Route path="proxies" element={<Proxies />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
