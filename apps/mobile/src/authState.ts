export type AuthenticationMode = "sign-in" | "sign-up";

export function isAuthenticationButtonSubmitting(
  submittingMode: AuthenticationMode | null,
  mode: AuthenticationMode,
): boolean {
  return submittingMode === mode;
}
