import { z } from "zod";

export const debateMessageSchema = z.object({
  id: z.string().min(1).max(100),
  role: z.enum(["bull", "bear", "judge"]),
  content: z.string().max(10_000),
  evidenceId: z.string().optional(),
});

export const debateRecordSchema = z.object({
  id: z.string().regex(/^[a-zA-Z0-9_-]{1,100}$/),
  ticker: z.string().regex(/^[A-Z.]{1,10}$/),
  title: z.string().max(200),
  createdAt: z.iso.datetime(),
  messages: z.array(debateMessageSchema).max(30),
  summary: z.string().max(10_000),
});

export const watchlistSchema = z.array(z.string().regex(/^[A-Z.]{1,10}$/)).max(50);
export const historySchema = z.array(debateRecordSchema).max(30);
