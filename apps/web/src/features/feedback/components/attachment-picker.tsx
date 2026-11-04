import { useRef, useState } from "react";
import { FileText, Paperclip, Upload, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { attachmentAccept, formatFileSize } from "../model/attachment-policy";
import type { Attachment } from "../model/attachment-policy";

type Props = {
  items: Attachment[];
  errors: string[];
  disabled: boolean;
  onAdd: (files: File[]) => void;
  onRemove: (id: string) => void;
};

export function AttachmentPicker({ items, errors, disabled, onAdd, onRemove }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  return (
    <div className="space-y-4">
      <div
        className={cn(
          "rounded-xl border border-dashed p-6 text-center transition-colors",
          dragging ? "border-primary bg-primary/5" : "bg-muted/20",
          disabled && "opacity-60",
        )}
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          if (!disabled) onAdd(Array.from(event.dataTransfer.files));
        }}
      >
        <Upload className="mx-auto mb-3 size-6 text-primary" aria-hidden="true" />
        <p className="text-sm font-medium">Drop a screenshot or document here</p>
        <p id="attachment-help" className="mt-1 text-xs leading-relaxed text-muted-foreground">
          PDF, PNG or JPEG · up to 3 files
          <br />5 MiB per file · 10 MiB combined
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-4"
          disabled={disabled}
          onClick={() => input.current?.click()}
        >
          <Paperclip className="size-3.5" />
          Choose files
        </Button>
        <input
          ref={input}
          type="file"
          multiple
          accept={attachmentAccept}
          disabled={disabled}
          aria-label="Choose feedback attachments"
          aria-describedby="attachment-help"
          className="sr-only"
          tabIndex={-1}
          onChange={(event) => {
            onAdd(Array.from(event.target.files ?? []));
            event.target.value = "";
          }}
        />
      </div>
      {items.length > 0 && (
        <ul className="space-y-2" aria-label="Selected attachments">
          {items.map((item) => (
            <AttachmentRow key={item.id} item={item} disabled={disabled} onRemove={onRemove} />
          ))}
        </ul>
      )}
      {errors.length > 0 && (
        <ul role="alert" className="space-y-1 text-sm text-destructive">
          {errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AttachmentRow({
  item,
  disabled,
  onRemove,
}: {
  item: Attachment;
  disabled: boolean;
  onRemove: (id: string) => void;
}) {
  return (
    <li className="flex items-center gap-3 rounded-lg border p-3">
      {item.previewUrl ? (
        <img
          src={item.previewUrl}
          alt={`Preview of ${item.file.name}`}
          className="size-10 rounded object-cover"
        />
      ) : (
        <FileText className="size-8 shrink-0 text-muted-foreground" aria-hidden="true" />
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium" title={item.file.name}>
          {item.file.name}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          {formatFileSize(item.file.size)}
          {!item.file.type && " · Type not verified"}
        </p>
      </div>
      <Button
        type="button"
        size="icon"
        variant="ghost"
        className="size-9 shrink-0"
        disabled={disabled}
        aria-label={`Remove ${item.file.name}`}
        onClick={() => onRemove(item.id)}
      >
        <X className="size-4" />
      </Button>
    </li>
  );
}
