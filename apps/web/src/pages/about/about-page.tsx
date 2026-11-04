import { ArrowUpRight, Github } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeading } from "@/components/shared/status/page-heading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AboutPrinciples,
  DemoBoundaries,
  ResearchJourney,
  TechnologyChoices,
} from "./about-sections";

const sourceUrl = "https://github.com/hahaArthur17/ai-bull-vs-bear/tree/codex/web-portfolio";

export function AboutPage() {
  return (
    <div className="page-content space-y-10">
      <PageHeading
        eyebrow="Behind the perspective"
        title="A little more context."
        description="Counterpoint is a frontend portfolio project exploring how thoughtful interfaces can make competing ideas easier to understand."
        actions={
          <Button asChild variant="outline" size="sm">
            <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
              <Github className="size-4" />
              View source
              <ArrowUpRight className="size-3" />
            </a>
          </Button>
        }
      />
      <section
        className="grid gap-7 border-y py-9 lg:grid-cols-[1.1fr_1fr]"
        aria-labelledby="product-idea"
      >
        <div>
          <Badge variant="secondary" className="mb-5">
            Bull vs Bear Research
          </Badge>
          <h2
            id="product-idea"
            className="font-editorial max-w-xl text-3xl leading-tight sm:text-4xl"
          >
            Good research leaves room for another view.
          </h2>
        </div>
        <div className="space-y-4 text-sm leading-relaxed text-muted-foreground">
          <p>
            A single conclusion can hide the assumptions behind it. Counterpoint brings a
            constructive case, a cautious case, and their supporting context into one calm
            workspace.
          </p>
          <p>
            The product follows a simple idea: explore a company, compare interpretations, inspect
            the evidence, and return to what you learned. The goal is a clearer research experience,
            with uncertainty kept in view.
          </p>
          <Button asChild variant="link" className="h-auto px-0">
            <Link to="/stocks/AAPL">
              Explore a sample company
              <ArrowUpRight className="size-4" />
            </Link>
          </Button>
        </div>
      </section>
      <ResearchJourney />
      <AboutPrinciples />
      <TechnologyChoices />
      <DemoBoundaries />
    </div>
  );
}
