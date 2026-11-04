import { useEffect } from "react";
import { UserRound } from "lucide-react";
import { Link, Outlet, ScrollRestoration, useLocation } from "react-router-dom";
import { config } from "@/app/config/env";
import { Brand } from "./brand";
import { Navigation, SidebarNote } from "./navigation";
import { AppHeader } from "./app-header";

export function AppLayout() {
  const { pathname } = useLocation();
  useEffect(() => {
    document.title = `${pathname.startsWith("/feedback") ? "Send feedback" : pathname.startsWith("/user") ? "Your space" : pathname.startsWith("/history") ? "Research history" : "Research workspace"} — Counterpoint`;
  }, [pathname]);
  return (
    <div className="app-grid">
      <a
        href="#main-content"
        className="fixed left-4 top-3 z-50 -translate-y-24 rounded-md bg-primary px-4 py-3 text-sm text-primary-foreground focus:translate-y-0"
      >
        Skip to content
      </a>
      <aside className="app-sidebar">
        <Brand />
        <Navigation />
        <SidebarNote />
        <Link to="/user" className="mt-6 flex items-center gap-3 px-2">
          <span className="flex size-9 items-center justify-center rounded-full bg-secondary text-sm">
            <UserRound className="size-4" aria-hidden="true" />
          </span>
          <span className="text-xs">
            <span className="block font-medium">Your guest workspace</span>
            <span className="mt-1 block text-[10px] text-muted-foreground">
              Curiosity, welcome here.
            </span>
          </span>
        </Link>
      </aside>
      <div className="min-w-0">
        <AppHeader />
        <main id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
        <footer className="flex flex-wrap justify-between gap-3 border-t px-6 py-5 text-[10px] text-muted-foreground md:px-11">
          <span>© {new Date().getFullYear()} Counterpoint · Built for a wider perspective.</span>
          <span>
            {config.dataMode === "demo" ? "Simulated research data" : "Connected research"} ·
            Educational demonstration
          </span>
        </footer>
      </div>
      <ScrollRestoration getKey={(location) => location.pathname} />
    </div>
  );
}
