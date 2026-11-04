import { useState } from "react";
import { Menu, Moon, Sun, ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
  SheetDescription,
} from "@/components/ui/sheet";
import { useTheme } from "@/app/providers/theme-context";
import { config } from "@/app/config/env";
import { Brand } from "./brand";
import { Navigation } from "./navigation";
import { GlobalSearch } from "./global-search";

export function AppHeader() {
  const { theme, setTheme } = useTheme();
  return (
    <header className="app-topbar">
      <div className="flex items-center gap-3">
        <MobileNavigation />
        <Link
          to="/"
          className="text-sm font-semibold tracking-tight md:hidden"
          aria-label="Counterpoint home"
        >
          counterpoint.
        </Link>
        <p className="hidden text-[11px] text-muted-foreground xl:block">
          A clearer perspective starts here.
        </p>
        <span className="demo-pill hidden sm:inline-flex">
          <span className="demo-dot" />
          {config.dataMode === "demo" ? "Demo research" : "Connected research"}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <GlobalSearch />
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </Button>
        <Button asChild size="sm" className="hidden text-xs sm:inline-flex">
          <Link to="/stocks/AAPL">
            Explore research <ArrowUpRight className="size-3" />
          </Link>
        </Button>
      </div>
    </header>
  );
}

function MobileNavigation() {
  const [open, setOpen] = useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open navigation">
          <Menu />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-72 p-6">
        <SheetTitle className="sr-only">Navigation</SheetTitle>
        <SheetDescription className="sr-only">
          Explore research, history and your workspace preferences.
        </SheetDescription>
        <Brand />
        <Navigation onNavigate={() => setOpen(false)} />
      </SheetContent>
    </Sheet>
  );
}
