import { useState } from "react";
import { useIsMutating, useQueryClient } from "@tanstack/react-query";
import { RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { resetDemoState } from "@/mocks/state/scenarios";

export function ResetDemoDialog({ onReset }: { onReset: () => void }) {
  const client = useQueryClient();
  const mutations = useIsMutating();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  async function reset() {
    setPending(true);
    try {
      await Promise.all([
        client.cancelQueries({ queryKey: ["watchlist"] }),
        client.cancelQueries({ queryKey: ["history"] }),
      ]);
      resetDemoState();
      onReset();
      await Promise.all([
        client.resetQueries({ queryKey: ["watchlist"] }),
        client.resetQueries({ queryKey: ["history"] }),
        client.invalidateQueries({ queryKey: ["stocks"] }),
      ]);
      setOpen(false);
      toast.success("Your demo has a fresh start", {
        description: "The starting watchlist and sample sessions are restored.",
      });
    } catch {
      toast.error("The demo could not be refreshed. Please try again.");
    } finally {
      setPending(false);
    }
  }
  return (
    <AlertDialog
      open={open}
      onOpenChange={(value) => {
        if (!pending) setOpen(value);
      }}
    >
      <AlertDialogTrigger asChild>
        <Button variant="outline" size="sm" disabled={mutations > 0}>
          <RotateCcw className="size-3.5" />
          Reset demo
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Start with a fresh workspace?</AlertDialogTitle>
          <AlertDialogDescription>
            This removes the demo watchlist and replay history saved in this browser, then restores
            the sample collection. Your appearance preference stays the same.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>Keep my workspace</AlertDialogCancel>
          <Button onClick={() => void reset()} disabled={pending || mutations > 0}>
            {pending ? "Resetting…" : "Reset demo data"}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
