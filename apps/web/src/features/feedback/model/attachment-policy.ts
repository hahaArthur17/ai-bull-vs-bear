export const attachmentLimits = { count: 3, individual: 5 * 1024 ** 2, total: 10 * 1024 ** 2 };
export const attachmentAccept = ".pdf,.png,.jpg,.jpeg";

const mimeByExtension: Record<string, string> = {
  pdf: "application/pdf",
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
};

export type AttachmentIssue = {
  code: "type" | "size" | "total" | "count" | "empty" | "duplicate";
  message: string;
};
export type FileMetadata = Pick<File, "name" | "size" | "type" | "lastModified">;
export type Attachment = { id: string; file: File; previewUrl?: string };

export function fileIdentity(file: FileMetadata) {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

export function validateFile(file: FileMetadata): AttachmentIssue | undefined {
  const expected = mimeByExtension[file.name.split(".").at(-1)?.toLowerCase() ?? ""];
  if (!expected || (file.type && file.type !== expected))
    return { code: "type", message: `${file.name}: choose a PDF, PNG or JPEG file.` };
  if (!file.size) return { code: "empty", message: `${file.name}: this file is empty.` };
  if (file.size > attachmentLimits.individual)
    return { code: "size", message: `${file.name}: the limit is 5 MiB per file.` };
}

export function acceptAttachments(current: FileMetadata[], incoming: File[]) {
  const accepted: File[] = [];
  const issues: AttachmentIssue[] = [];
  let total = current.reduce((sum, file) => sum + file.size, 0);
  for (const file of incoming) {
    const existing = [...current, ...accepted];
    const issue =
      validateFile(file) ??
      (existing.some((item) => fileIdentity(item) === fileIdentity(file))
        ? { code: "duplicate" as const, message: `${file.name}: this file is already selected.` }
        : undefined) ??
      (existing.length >= attachmentLimits.count
        ? { code: "count" as const, message: `${file.name}: you can attach up to 3 files.` }
        : undefined) ??
      (total + file.size > attachmentLimits.total
        ? { code: "total" as const, message: `${file.name}: the combined limit is 10 MiB.` }
        : undefined);
    if (issue) {
      issues.push(issue);
      continue;
    }
    accepted.push(file);
    total += file.size;
  }
  return { accepted, issues };
}

export function formatFileSize(bytes: number) {
  return bytes >= 1024 ** 2
    ? `${(bytes / 1024 ** 2).toFixed(1)} MiB`
    : `${Math.max(1, Math.ceil(bytes / 1024))} KiB`;
}
