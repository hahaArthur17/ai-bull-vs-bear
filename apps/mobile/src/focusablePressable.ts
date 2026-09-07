import { colors, interaction } from "./theme/tokens.ts";

/**
 * Shared focus treatment for controls that render through React Native Web.
 *
 * The returned style is intentionally null outside keyboard focus so existing
 * native, disabled, and pressed styles keep their current precedence.
 */
export function focusablePressableStyle(
  focused: boolean,
  disabled = false,
) {
  if (!focused || disabled) return null;
  return {
    borderColor: colors.action.focus,
    borderWidth: interaction.focusRingWidth,
  } as const;
}
