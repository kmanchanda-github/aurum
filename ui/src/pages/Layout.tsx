import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { clearToken } from "@/lib/auth";
import { useAdminAuth } from "@/hooks/useAdminAuth";
import {
  BarChart3,
  Bot,
  Goal,
  LineChart,
  LogOut,
  Newspaper,
  Settings,
  ShieldCheck,
} from "lucide-react";

const BASE_NAV = [
  { to: "/", icon: Bot, label: "Chat" },
  { to: "/portfolio", icon: BarChart3, label: "Portfolio" },
  { to: "/market", icon: LineChart, label: "Market" },
  { to: "/goals", icon: Goal, label: "Goals" },
  { to: "/news", icon: Newspaper, label: "News" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export default function Layout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { isAdmin } = useAdminAuth();

  const NAV = isAdmin
    ? [...BASE_NAV, { to: "/admin", icon: ShieldCheck, label: "Admin" }]
    : BASE_NAV;

  const logout = () => {
    clearToken();
    navigate("/login");
  };

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-16 md:w-56 bg-gray-900 text-white flex flex-col shrink-0">
        <div className="p-4 border-b border-gray-700 flex items-center gap-2">
          <span className="text-2xl">⚜️</span>
          <span className="hidden md:block font-bold text-lg text-gold-400">Aurum</span>
        </div>
        <nav className="flex-1 py-4 space-y-1 px-2">
          {NAV.map(({ to, icon: Icon, label }) => {
            const active = pathname === to || (to !== "/" && pathname.startsWith(to));
            return (
              <Link
                key={to}
                to={to}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm font-medium ${
                  active
                    ? "bg-gold-600 text-white"
                    : "text-gray-300 hover:bg-gray-800 hover:text-white"
                }`}
              >
                <Icon size={18} />
                <span className="hidden md:block">{label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="p-2 border-t border-gray-700">
          <button
            onClick={logout}
            className="flex items-center gap-3 px-3 py-2.5 w-full rounded-lg text-gray-300 hover:bg-gray-800 hover:text-white transition-colors text-sm"
          >
            <LogOut size={18} />
            <span className="hidden md:block">Logout</span>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-hidden flex flex-col">
        <Outlet />
      </main>
    </div>
  );
}
