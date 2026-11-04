import { describe, expect, it } from "vitest";
import { acceptAttachments, attachmentLimits, validateFile } from "../model/attachment-policy";

const file = (name: string, size: number, type = "application/pdf", lastModified = 1) =>
  ({ name, size, type, lastModified }) as File;

describe("attachment rules", () => {
  it("accepts exact individual and combined limits", () => {
    const result = acceptAttachments(
      [],
      [file("one.pdf", attachmentLimits.individual), file("two.pdf", attachmentLimits.individual)],
    );
    expect(result.accepted).toHaveLength(2);
    expect(result.issues).toHaveLength(0);
  });

  it("rejects one byte beyond either limit without discarding valid files", () => {
    expect(validateFile(file("big.pdf", attachmentLimits.individual + 1))?.code).toBe("size");
    const current = [
      file("one.pdf", attachmentLimits.individual),
      file("two.pdf", attachmentLimits.individual),
    ];
    const result = acceptAttachments(current, [file("tiny.pdf", 1)]);
    expect(result.issues[0].code).toBe("total");
    expect(current).toHaveLength(2);
  });

  it("limits count and recognises duplicate metadata", () => {
    const current = [file("one.pdf", 1), file("two.pdf", 1), file("three.pdf", 1)];
    expect(acceptAttachments(current, [file("four.pdf", 1)]).issues[0].code).toBe("count");
    expect(acceptAttachments([current[0]], [current[0]]).issues[0].code).toBe("duplicate");
  });

  it("rejects empty and mismatched files, allowing missing MIME with a known extension", () => {
    expect(validateFile(file("empty.pdf", 0))?.code).toBe("empty");
    expect(validateFile(file("photo.png", 100, "application/pdf"))?.code).toBe("type");
    expect(validateFile(file("script.exe", 100, ""))?.code).toBe("type");
    expect(validateFile(file("photo.PNG", 100, ""))).toBeUndefined();
  });
});
