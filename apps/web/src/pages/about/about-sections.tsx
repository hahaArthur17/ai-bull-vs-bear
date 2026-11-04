import { ArrowRight, BookOpen, ChartNoAxesCombined, MessagesSquare } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

const journey = [
  {
    label: "Explore",
    detail: "Search companies, save a watchlist, and examine a year of synthetic price history.",
    icon: ChartNoAxesCombined,
  },
  {
    label: "Compare",
    detail:
      "Follow a scripted Bull and Bear conversation at your own pace, with room to pause and reflect.",
    icon: MessagesSquare,
  },
  {
    label: "Examine",
    detail:
      "Open the supporting context, read the assumptions, and revisit a saved research session.",
    icon: BookOpen,
  },
];

export function ResearchJourney() {
  return (
    <section aria-labelledby="research-journey" className="space-y-5">
      <h2 id="research-journey" className="section-title">
        A path from curiosity to context.
      </h2>
      <div className="grid gap-4 md:grid-cols-3">
        {journey.map(({ label, detail, icon: Icon }, index) => (
          <Card key={label} className="gap-0 shadow-none">
            <CardContent>
              <div className="mb-5 flex items-center justify-between">
                <Icon className="size-5 text-primary" aria-hidden="true" />
                <span className="numeric text-xs text-muted-foreground">0{index + 1}</span>
              </div>
              <h3 className="mb-3 font-medium">{label}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{detail}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}

export function AboutPrinciples() {
  return (
    <section
      aria-labelledby="design-principles"
      className="grid gap-6 py-2 lg:grid-cols-[0.7fr_1fr]"
    >
      <div>
        <p className="eyebrow mb-3">The design perspective</p>
        <h2 id="design-principles" className="font-editorial text-3xl">
          Calm, clear, considered.
        </h2>
      </div>
      <dl className="divide-y text-sm">
        <Principle
          title="A hierarchy that helps"
          detail="Editorial headings introduce the subject; restrained color and consistent spacing give the actual research room to breathe."
        />
        <Principle
          title="Useful, responsive interactions"
          detail="Search, saved states, chart exploration, and replay controls each give a clear response. Loading and failure are part of the experience, too."
        />
        <Principle
          title="Different ways to explore"
          detail="Responsive layouts, keyboard access, visible focus, and a table alongside the chart provide more than one way through the content."
        />
      </dl>
    </section>
  );
}

function Principle({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="py-5 first:pt-0 last:pb-0">
      <dt className="font-medium">{title}</dt>
      <dd className="mt-2 leading-relaxed text-muted-foreground">{detail}</dd>
    </div>
  );
}

export function TechnologyChoices() {
  return (
    <section aria-labelledby="technology-choices" className="rounded-xl border bg-card p-6 sm:p-7">
      <p className="eyebrow mb-3">Under the surface</p>
      <h2 id="technology-choices" className="section-title">
        Built with an eye on the details.
      </h2>
      <div className="mt-5 flex flex-wrap gap-2">
        {["React", "TypeScript", "Vite", "Tailwind CSS", "shadcn/ui", "TanStack Query", "MSW"].map(
          (tool) => (
            <Badge key={tool} variant="outline">
              {tool}
            </Badge>
          ),
        )}
      </div>
      <p className="mt-5 max-w-3xl text-sm leading-relaxed text-muted-foreground">
        The Web interface uses reusable components and typed feature boundaries. A separate
        data-access layer connects the public demo to predictable simulated APIs, while leaving
        space for the existing backend to be integrated later.
      </p>
      <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted-foreground">
        The feedback form explores field validation, optional identity details, file selection,
        cancellation, and clear submission states. The interface distinguishes a local simulation
        from a configured real receiver.
      </p>
    </section>
  );
}

export function DemoBoundaries() {
  return (
    <section aria-labelledby="demo-boundaries" className="space-y-4 pb-2">
      <h2 id="demo-boundaries" className="section-title">
        A demonstration, with clear boundaries.
      </h2>
      <ul className="grid gap-3 text-sm leading-relaxed text-muted-foreground sm:grid-cols-2">
        {[
          "Prices, company metrics, and evidence excerpts in the public Demo are fictional. The synthetic dataset is dated October 30, 2026.",
          "The conversation is a scripted replay. It does not call a live AI model, quote real filings, or generate personalized investment advice.",
          "Demo watchlists and replay history live in this browser. Visitors do not share accounts or saved information.",
          "The existing backend is retained for future integration. Modules that are not connected show an explicit message rather than simulated live results.",
        ].map((detail) => (
          <li key={detail} className="flex gap-3">
            <ArrowRight className="mt-1 size-3.5 shrink-0 text-primary" aria-hidden="true" />
            <span>{detail}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
