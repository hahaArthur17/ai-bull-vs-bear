import { ChartNoAxesCombined } from "lucide-react";
import { Link } from "react-router-dom";

export function Brand() {
  return (
    <Link to="/" className="brand-lockup" aria-label="Counterpoint home">
      <span className="brand-mark">
        <ChartNoAxesCombined className="size-5" />
      </span>
      <span>
        <span className="brand-name">
          counterpoint<span className="text-primary">.</span>
        </span>
        <span className="mt-0.5 block text-[8px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
          Bull vs Bear Research
        </span>
      </span>
    </Link>
  );
}
