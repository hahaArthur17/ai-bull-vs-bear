import {
  ArrowUpRight,
  ChartNoAxesCombined,
  Clock3,
  LayoutDashboard,
  LibraryBig,
  UserRound,
} from "lucide-react";
import { NavLink, Link } from "react-router-dom";
import { cn } from "@/lib/utils";

const mainItems = [
  { to: "/", label: "Workspace", icon: LayoutDashboard, end: true },
  { to: "/stocks/AAPL", label: "Stock research", icon: ChartNoAxesCombined },
  { to: "/history", label: "Research history", icon: Clock3 },
];
const personalItems = [
  { to: "/user", label: "Your space", icon: UserRound },
  { to: "/about", label: "About the project", icon: LibraryBig },
];

export function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="side-nav" aria-label="Main navigation">
      <p className="nav-section !mt-0">Explore</p>
      {mainItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={({ isActive }) => cn("nav-link", isActive && "active")}
        >
          <item.icon className="size-[17px]" />
          {item.label}
        </NavLink>
      ))}
      <p className="nav-section">Your workspace</p>
      {personalItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          onClick={onNavigate}
          className={({ isActive }) => cn("nav-link", isActive && "active")}
        >
          <item.icon className="size-[17px]" />
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}

export function SidebarNote() {
  return (
    <div className="side-note">
      <p className="text-[9px] font-semibold uppercase tracking-widest">A wider perspective</p>
      <p className="font-editorial my-3 text-[22px] leading-tight">
        Good research
        <br />
        considers both sides.
      </p>
      <Link
        to="/about"
        className="relative z-10 inline-flex items-center gap-2 text-[11px] font-medium"
      >
        Meet the project <ArrowUpRight className="size-3" />
      </Link>
    </div>
  );
}
