import { Bookmark, BookmarkCheck } from "lucide-react";
import { toast } from "sonner";
import { useIsMutating } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { useToggleWatchlist, useWatchlist } from "../hooks";

export function WatchlistButton({
  ticker,
  compact = false,
}: {
  ticker: string;
  compact?: boolean;
}) {
  const watchlist = useWatchlist();
  const mutation = useToggleWatchlist();
  const busy = useIsMutating({ mutationKey: ["watchlist", "toggle"] }) > 0;
  const watched = watchlist.data?.includes(ticker) ?? false;
  const label = `${watched ? "Remove" : "Add"} ${ticker} ${watched ? "from" : "to"} watchlist`;
  function toggle() {
    mutation.mutate(ticker, {
      onSuccess: () =>
        toast.success(
          watched ? `${ticker} removed from your watchlist` : `${ticker} saved to your watchlist`,
        ),
      onError: (error) => toast.error(error.message),
    });
  }
  return (
    <Button
      variant={compact ? "ghost" : "outline"}
      size={compact ? "icon" : "sm"}
      disabled={busy || watchlist.isPending || watchlist.isError}
      onClick={toggle}
      aria-label={label}
      aria-pressed={watched}
      className={compact ? "text-muted-foreground hover:text-primary" : "gap-2"}
    >
      {watched ? (
        <BookmarkCheck className="size-4 text-primary" />
      ) : (
        <Bookmark className="size-4" />
      )}
      {!compact && (watched ? "Saved to watchlist" : "Add to watchlist")}
    </Button>
  );
}
