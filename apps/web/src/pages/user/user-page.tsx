import { useEffect } from "react";
import { Bookmark, History, UserRound } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import config from "@/app/config/env";
import { PageHeading } from "@/components/shared/status/page-heading";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { useHistory } from "@/features/history/hooks";
import { useWatchlist } from "@/features/watchlist/hooks";
import { FeedbackCallout } from "./feedback-callout";
import { PreferencesPanel } from "./preferences-panel";

export function UserPage() {
  const watchlist = useWatchlist();
  const history = useHistory();
  const { hash } = useLocation();
  useEffect(() => {
    if (hash === "#feedback")
      document.getElementById("feedback")?.scrollIntoView({ block: "start" });
  }, [hash]);

  return (
    <div className="page-content space-y-8">
      <PageHeading
        eyebrow="Make yourself at home"
        title="Your workspace."
        description="A place for your curiosity, your saved perspectives, and the little things that make research feel yours."
      />
      <Card className="gap-0 shadow-none">
        <CardContent className="flex flex-wrap items-center gap-5">
          <span className="flex size-16 shrink-0 items-center justify-center rounded-2xl bg-secondary text-primary">
            <UserRound className="size-7" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="section-title">Guest workspace</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              No account needed. Start exploring, and keep the perspectives that interest you.
            </p>
          </div>
          <Badge variant="secondary" className="self-start">
            {config.dataMode === "demo" ? "Demo visitor" : "API preview"}
          </Badge>
        </CardContent>
      </Card>
      <div className="grid gap-4 sm:grid-cols-2">
        <WorkspaceCount
          label="Saved stocks"
          value={watchlist.data?.length}
          pending={watchlist.isPending}
          failed={watchlist.isError}
          href="/"
          icon="watchlist"
        />
        <WorkspaceCount
          label="Research sessions"
          value={history.data?.length}
          pending={history.isPending}
          failed={history.isError}
          href="/history"
          icon="history"
        />
      </div>
      <PreferencesPanel />
      <StorageNote />
      <FeedbackCallout />
    </div>
  );
}

function WorkspaceCount({
  label,
  value,
  pending,
  failed,
  href,
  icon,
}: {
  label: string;
  value?: number;
  pending: boolean;
  failed: boolean;
  href: string;
  icon: "watchlist" | "history";
}) {
  const Icon = icon === "watchlist" ? Bookmark : History;
  return (
    <Link
      to={href}
      className="group flex items-center gap-4 rounded-xl border bg-card p-5 transition-colors hover:border-primary/35"
    >
      <Icon className="size-5 text-primary" aria-hidden="true" />
      <div className="flex-1">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="numeric mt-1 text-2xl font-semibold" aria-live="polite">
          {pending ? "…" : failed ? "—" : (value ?? 0)}
        </p>
      </div>
      <span className="text-xs text-muted-foreground group-hover:text-primary">
        {failed ? "Not connected" : "View"}
      </span>
    </Link>
  );
}

function StorageNote() {
  return (
    <section aria-labelledby="local-data-heading" className="max-w-3xl space-y-3 px-1 py-3">
      <h2 id="local-data-heading" className="section-title">
        A little clarity about your data.
      </h2>
      <p className="text-sm leading-relaxed text-muted-foreground">
        In Demo mode, your watchlist and scripted replay history are saved only in this browser.
        They are not shared between devices or visitors. Your appearance preference is saved here,
        too.
      </p>
      <p className="text-sm leading-relaxed text-muted-foreground">
        Feedback drafts and selected files stay in memory until you leave or reset the form. The
        feedback page clearly labels whether you are trying a local demo or using a configured
        receiver.
      </p>
    </section>
  );
}
