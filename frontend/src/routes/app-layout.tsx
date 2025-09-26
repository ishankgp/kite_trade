import { Outlet, NavLink } from "react-router-dom";
import { Gauge, Layers, Settings, Wand2 } from "lucide-react";

function AppLayout() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b bg-white">
        <div className="container flex items-center justify-between py-4">
          <div className="flex items-center gap-3">
            <Gauge className="h-6 w-6 text-blue-600" />
            <div>
              <h1 className="text-lg font-semibold text-slate-900">
                @nifty_ml Dashboard
              </h1>
              <p className="text-sm text-slate-500">
                Market data explorer powered by Kite historical API
              </p>
            </div>
          </div>
          <nav className="flex items-center gap-6 text-sm font-medium text-slate-600">
            <NavLink
              to="/"
              className={({ isActive }) =>
                `flex items-center gap-2 transition-colors hover:text-slate-900 ${
                  isActive ? "text-slate-900" : ""
                }`
              }
              end
            >
              <Layers className="h-4 w-4" /> Instruments
            </NavLink>
            <NavLink
              to="/training"
              className={({ isActive }) =>
                `flex items-center gap-2 transition-colors hover:text-slate-900 ${
                  isActive ? "text-slate-900" : ""
                }`
              }
            >
              <Wand2 className="h-4 w-4" /> Training
            </NavLink>
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                `flex items-center gap-2 transition-colors hover:text-slate-900 ${
                  isActive ? "text-slate-900" : ""
                }`
              }
            >
              <Settings className="h-4 w-4" /> Settings
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="container py-10">
        <Outlet />
      </main>
    </div>
  );
}

export default AppLayout;


