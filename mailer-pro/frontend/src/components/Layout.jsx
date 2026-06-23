import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import {
  LayoutDashboard, Users, Mail, List, Globe, Tag, Megaphone,
  Send, AlertOctagon, BarChart2, LogOut, ChevronRight,
} from "lucide-react";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/accounts", label: "Accounts", icon: Users },
  { to: "/groups", label: "Groups", icon: List },
  { to: "/recipients", label: "Recipients", icon: Mail },
  { to: "/affiliates", label: "Affiliates", icon: Globe },
  { to: "/offers", label: "Offers", icon: Tag },
  { to: "/campaigns", label: "Campaigns", icon: Megaphone },
  { to: "/send", label: "Send", icon: Send },
  { to: "/blacklist", label: "Blacklist", icon: AlertOctagon },
  { to: "/stats", label: "Stats", icon: BarChart2 },
];

export default function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Sidebar */}
      <aside className="w-56 bg-gray-900 flex flex-col shrink-0">
        <div className="px-4 py-5 border-b border-gray-700">
          <span className="text-white font-bold text-lg tracking-tight">MailerPro</span>
        </div>
        <nav className="flex-1 overflow-y-auto py-2">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                  isActive
                    ? "bg-blue-600 text-white"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-gray-700">
          <div className="text-xs text-gray-400 mb-1">{user?.email}</div>
          <button
            onClick={logout}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-red-400 transition-colors"
          >
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
