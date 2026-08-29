import type { ExaminationResponse } from "./types";

export type ExaminationQuestionType = ExaminationResponse["question_type"];

export function canSubmitExamination(pendingQuestion: ExaminationQuestionType | null): boolean {
  return pendingQuestion === null;
}
