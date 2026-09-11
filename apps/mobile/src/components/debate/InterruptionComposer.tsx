import React from "react";
import { ActivityIndicator, StyleSheet, Text, TextInput, View } from "react-native";

import { FocusablePressable } from "../common";
import { colors, interaction, radii, spacing, typography } from "../../theme";

export const INTERRUPTION_VIEWPOINT_MAX_CODEPOINTS = 500;

export type InterruptionComposerBusy = "save" | "continue" | "end" | null;

export type InterruptionComposerProps = {
  value: string;
  onChange: (value: string) => void;
  onExplainStoppedText: () => void;
  onSave: () => void;
  onContinue: () => void;
  onEnd: () => void;
  busy: InterruptionComposerBusy;
  saved: boolean;
  error?: string;
  canExplainStoppedText: boolean;
  canContinue: boolean;
};

/** Keep the client-side limit aligned with the API's code point contract. */
export function truncateInterruptionViewpoint(
  value: string,
  maxCodePoints = INTERRUPTION_VIEWPOINT_MAX_CODEPOINTS,
): string {
  if (Array.from(value).length <= maxCodePoints) return value;
  return Array.from(value).slice(0, maxCodePoints).join("");
}

export function InterruptionComposer({
  value,
  onChange,
  onExplainStoppedText,
  onSave,
  onContinue,
  onEnd,
  busy,
  saved,
  error,
  canExplainStoppedText,
  canContinue,
}: InterruptionComposerProps) {
  const displayedValue = truncateInterruptionViewpoint(value);
  const codePointCount = Array.from(displayedValue).length;
  const isBusy = busy !== null;
  const hasViewpoint = displayedValue.trim().length > 0;
  const atLimit = codePointCount >= INTERRUPTION_VIEWPOINT_MAX_CODEPOINTS;
  const saveDisabled = isBusy || !hasViewpoint || saved;
  const continueDisabled = isBusy || !canContinue || !saved;

  return (
    <View style={styles.card} accessibilityLabel="Interruption response">
      <Text style={styles.eyebrow}>INTERRUPTION · YOUR INPUT</Text>
      <Text accessibilityRole="header" style={styles.title}>Add your point before deciding.</Text>
      <Text style={styles.intro}>
        Save your viewpoint as context for this interruption. Saving does not call the model; Continue resumes the debate explicitly.
      </Text>

      {canExplainStoppedText ? (
        <FocusablePressable
          accessibilityHint="Opens a read-only explanation without resuming or changing the debate."
          accessibilityLabel="Explain stopped text"
          accessibilityRole="button"
          accessibilityState={{ disabled: isBusy }}
          disabled={isBusy}
          onPress={onExplainStoppedText}
          style={[styles.explainButton, isBusy && styles.disabledButton]}
        >
          <Text style={styles.explainButtonText}>Explain stopped text</Text>
        </FocusablePressable>
      ) : (
        <Text style={styles.explainUnavailable}>
          No text was shown before this stop, so there is nothing to explain.
        </Text>
      )}

      <Text nativeID="interruption-viewpoint-label" style={styles.label}>YOUR VIEWPOINT</Text>
      <TextInput
        accessibilityLabel="Your viewpoint"
        accessibilityLabelledBy="interruption-viewpoint-label"
        accessibilityHint="Write a question or opinion for the interrupted debate."
        editable={!isBusy}
        multiline
        onChangeText={(nextValue) => onChange(truncateInterruptionViewpoint(nextValue))}
        placeholder="What should the debate consider when it resumes?"
        placeholderTextColor={colors.content.secondary}
        style={styles.input}
        textAlignVertical="top"
        value={displayedValue}
      />
      <View style={styles.inputMeta}>
        <Text style={styles.counter}>
          {codePointCount}/{INTERRUPTION_VIEWPOINT_MAX_CODEPOINTS} characters
        </Text>
        {saved ? <Text accessibilityLiveRegion="polite" style={styles.saved}>Saved</Text> : null}
      </View>
      {atLimit ? (
        <Text style={styles.limitNote}>
          You have reached the 500-character limit.
        </Text>
      ) : null}

      {error ? (
        <Text accessibilityLiveRegion="assertive" style={styles.error}>{error}</Text>
      ) : null}

      <FocusablePressable
        accessibilityHint="Saves your viewpoint as context without calling the model."
        accessibilityLabel="Save viewpoint"
        accessibilityRole="button"
        accessibilityState={{ busy: busy === "save", disabled: saveDisabled }}
        disabled={saveDisabled}
        onPress={onSave}
        style={[styles.primaryButton, saveDisabled && styles.disabledButton]}
      >
        {busy === "save" ? <ActivityIndicator color={colors.content.onSignal} size="small" /> : null}
        <Text style={styles.primaryButtonText}>{busy === "save" ? "Saving…" : saved ? "Viewpoint saved" : "Save viewpoint"}</Text>
      </FocusablePressable>

      <FocusablePressable
        accessibilityHint="Resumes the debate using the saved viewpoint."
        accessibilityLabel="Continue with my point"
        accessibilityRole="button"
        accessibilityState={{ busy: busy === "continue", disabled: continueDisabled }}
        disabled={continueDisabled}
        onPress={onContinue}
        style={[styles.continueButton, continueDisabled && styles.disabledButton]}
      >
        {busy === "continue" ? <ActivityIndicator color={colors.content.inverse} size="small" /> : null}
        <Text style={styles.continueButtonText}>{busy === "continue" ? "Continuing…" : "Continue with my point"}</Text>
      </FocusablePressable>
      {!canContinue ? (
        <Text style={styles.continueNote}>
          Continue is available after the interrupted job has finished.
        </Text>
      ) : !saved ? (
        <Text style={styles.continueNote}>
          Save your viewpoint before continuing.
        </Text>
      ) : null}

      <FocusablePressable
        accessibilityHint="Ends the debate at this interruption point."
        accessibilityLabel="End debate"
        accessibilityRole="button"
        accessibilityState={{ busy: busy === "end", disabled: isBusy }}
        disabled={isBusy}
        onPress={onEnd}
        style={[styles.endButton, isBusy && styles.disabledButton]}
      >
        {busy === "end" ? <ActivityIndicator color={colors.content.danger} size="small" /> : null}
        <Text style={styles.endButtonText}>{busy === "end" ? "Ending…" : "End debate"}</Text>
      </FocusablePressable>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface.raised,
    borderColor: colors.border.subtle,
    borderRadius: radii.lg,
    borderWidth: 1,
    padding: spacing.lg,
  },
  eyebrow: {
    color: colors.action.primary,
    fontSize: typography.label.fontSize,
    fontWeight: typography.label.fontWeight,
    letterSpacing: typography.label.letterSpacing,
  },
  title: {
    color: colors.content.primary,
    fontSize: typography.sectionTitle.fontSize,
    fontWeight: typography.sectionTitle.fontWeight,
    lineHeight: typography.sectionTitle.lineHeight,
    marginTop: spacing.xs,
  },
  intro: {
    color: colors.content.secondary,
    fontSize: typography.bodySmall.fontSize,
    lineHeight: typography.bodySmall.lineHeight,
    marginTop: spacing.sm,
  },
  label: {
    color: colors.content.secondary,
    fontSize: typography.label.fontSize,
    fontWeight: typography.label.fontWeight,
    letterSpacing: typography.label.letterSpacing,
    marginTop: spacing.lg,
    marginBottom: spacing.xs,
  },
  input: {
    backgroundColor: colors.surface.subtle,
    borderColor: colors.border.subtle,
    borderRadius: radii.md,
    borderWidth: 1,
    color: colors.content.primary,
    fontSize: typography.body.fontSize,
    lineHeight: typography.body.lineHeight,
    minHeight: 124,
    padding: spacing.md,
  },
  inputMeta: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: spacing.xs,
    minHeight: typography.bodySmall.lineHeight,
  },
  counter: {
    color: colors.content.secondary,
    fontSize: 11,
  },
  saved: {
    color: colors.action.secondary,
    fontSize: 11,
    fontWeight: "800",
  },
  limitNote: {
    color: colors.content.warning,
    fontSize: 11,
    lineHeight: 16,
    marginTop: spacing.xs,
  },
  error: {
    backgroundColor: colors.surface.danger,
    borderRadius: radii.sm,
    color: colors.content.danger,
    fontSize: 12,
    lineHeight: 18,
    marginTop: spacing.md,
    padding: spacing.sm,
  },
  explainButton: {
    alignItems: "center",
    borderColor: colors.action.primary,
    borderRadius: radii.md,
    borderWidth: 1,
    justifyContent: "center",
    marginTop: spacing.md,
    minHeight: interaction.minTargetSize,
    paddingHorizontal: spacing.md,
  },
  explainButtonText: {
    color: colors.action.primary,
    fontSize: 13,
    fontWeight: "800",
  },
  explainUnavailable: {
    color: colors.content.secondary,
    fontSize: 11,
    lineHeight: 16,
    marginTop: spacing.md,
  },
  primaryButton: {
    alignItems: "center",
    backgroundColor: colors.action.primary,
    borderRadius: radii.md,
    flexDirection: "row",
    gap: spacing.sm,
    justifyContent: "center",
    marginTop: spacing.md,
    minHeight: interaction.minTargetSize,
    paddingHorizontal: spacing.md,
  },
  primaryButtonText: {
    color: colors.content.onSignal,
    fontSize: 13,
    fontWeight: "800",
  },
  continueButton: {
    alignItems: "center",
    backgroundColor: colors.action.secondary,
    borderRadius: radii.md,
    flexDirection: "row",
    gap: spacing.sm,
    justifyContent: "center",
    marginTop: spacing.sm,
    minHeight: interaction.minTargetSize,
    paddingHorizontal: spacing.md,
  },
  continueButtonText: {
    color: colors.content.inverse,
    fontSize: 13,
    fontWeight: "800",
  },
  continueNote: {
    color: colors.content.secondary,
    fontSize: 11,
    lineHeight: 16,
    marginTop: spacing.xs,
  },
  endButton: {
    alignItems: "center",
    borderColor: colors.border.danger,
    borderRadius: radii.md,
    borderWidth: 1,
    flexDirection: "row",
    gap: spacing.sm,
    justifyContent: "center",
    marginTop: spacing.sm,
    minHeight: interaction.minTargetSize,
    paddingHorizontal: spacing.md,
  },
  endButtonText: {
    color: colors.content.danger,
    fontSize: 13,
    fontWeight: "800",
  },
  disabledButton: {
    opacity: 0.5,
  },
});
