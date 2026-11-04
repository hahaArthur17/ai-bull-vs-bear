import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import type { DebateRecord } from "@/lib/contracts/research";

export function HistoryDeleteDialog({
  record,
  pending,
  onCancel,
  onConfirm,
}: {
  record: DebateRecord | null;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog
      open={record !== null}
      onOpenChange={(open) => {
        if (!open && !pending) onCancel();
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="font-serif text-2xl">Remove this session?</AlertDialogTitle>
          <AlertDialogDescription>
            “{record?.title}” will be removed from your saved demonstration history. You can start
            another replay any time.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>Keep session</AlertDialogCancel>
          <AlertDialogAction
            disabled={pending}
            className="bg-destructive text-white hover:bg-destructive/90"
            onClick={(event) => {
              event.preventDefault();
              onConfirm();
            }}
          >
            {pending ? "Removing…" : "Remove session"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
