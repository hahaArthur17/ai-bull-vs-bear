import { useCallback, useEffect, useRef, useState } from "react";
import { acceptAttachments } from "../model/attachment-policy";
import type { Attachment } from "../model/attachment-policy";

function release(items: Attachment[]) {
  items.forEach((item) => {
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
  });
}

function createAttachment(file: File): Attachment {
  const isImage = /\.(png|jpe?g)$/i.test(file.name);
  return {
    id: crypto.randomUUID(),
    file,
    previewUrl:
      isImage && typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : undefined,
  };
}

export function useAttachmentQueue() {
  const [items, setItems] = useState<Attachment[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const current = useRef<Attachment[]>([]);
  const replace = useCallback((next: Attachment[]) => {
    current.current = next;
    setItems(next);
  }, []);
  const add = useCallback(
    (files: File[]) => {
      const result = acceptAttachments(
        current.current.map((item) => item.file),
        files,
      );
      setErrors(result.issues.map((issue) => issue.message));
      replace([...current.current, ...result.accepted.map(createAttachment)]);
    },
    [replace],
  );
  const remove = useCallback(
    (id: string) => {
      release(current.current.filter((item) => item.id === id));
      replace(current.current.filter((item) => item.id !== id));
      setErrors([]);
    },
    [replace],
  );
  const reset = useCallback(() => {
    release(current.current);
    replace([]);
    setErrors([]);
  }, [replace]);
  useEffect(() => () => release(current.current), []);
  return { items, errors, add, remove, reset };
}
