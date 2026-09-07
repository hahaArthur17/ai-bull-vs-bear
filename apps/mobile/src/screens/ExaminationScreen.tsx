import { useState } from "react";
import { ActivityIndicator, Linking, ScrollView, Text, View } from "react-native";

import { BackButton, FocusablePressable, LoadingView, SectionHeader } from "../components/common";
import { isSafeEvidenceDestination, presentEvidence } from "../evidencePresentation";
import { appStyles as styles, colors, interaction, palette, radii, spacing } from "../theme";
import type { Claim, EvidenceItem, ExaminationResponse } from "../types";

type ExaminationScreenProps = {
  claim: Claim | null;
  error: string;
  pendingQuestion: ExaminationResponse["question_type"] | null;
  result: ExaminationResponse | null;
  onBack: () => void;
  onAsk: (questionType: ExaminationResponse["question_type"]) => void;
};

const questions: ReadonlyArray<readonly [ExaminationResponse["question_type"], string]> = [
  ["evidence_support", "What evidence supports this?"],
  ["explain_term", "What does this term mean?"],
  ["signal_strength", "How strong is the signal?"],
  ["risk_meaning", "What is the risk meaning?"],
];

export function ExaminationScreen({ claim, error, pendingQuestion, result, onBack, onAsk }: ExaminationScreenProps) {
  if (!claim) return <LoadingView label="No claim selected." onBack={onBack} />;
  const submitting = pendingQuestion !== null;
  return (
    <ScrollView contentContainerStyle={[styles.page, styles.readingPage]}>
      <BackButton onPress={onBack} />
      <Text style={styles.eyebrow}>CROSS-EXAMINE A CLAIM</Text>
      <Text style={styles.detailTitle}>Cross Examination</Text>
      <View accessibilityLabel={`Selected ${claim.agent} claim`} style={[styles.answerCard, { borderColor: colors.border.warning, borderWidth: 1 }]}>
        <Text style={styles.cardLabel}>SELECTED {claim.agent.toUpperCase()} CLAIM</Text>
        <Text style={styles.cardTitle}>{claim.text}</Text>
        <View style={{ borderTopColor: colors.border.warning, borderTopWidth: 1, marginTop: spacing.sm, paddingTop: spacing.sm }}>
          <Text style={styles.evidenceIds}>Evidence IDs · {claim.evidence_ids.length ? claim.evidence_ids.join(" + ") : "No evidence IDs supplied"}</Text>
          <Text style={styles.evidenceIds}>Signal strength · {claim.signal_strength} · Confidence · {claim.confidence}</Text>
        </View>
      </View>
      <SectionHeader title="Ask a focused question" meta="explanation agent" />
      {questions.map(([type, label]) => (
        <FocusablePressable
          key={type}
          accessibilityHint="Requests an explanation of the selected claim without changing the Debate."
          accessibilityRole="button"
          accessibilityState={{ busy: pendingQuestion === type, disabled: submitting }}
          disabled={submitting}
          style={[styles.questionButton, { minHeight: interaction.minTargetSize }, submitting && styles.questionButtonDisabled]}
          onPress={() => onAsk(type)}
        >
          {pendingQuestion === type ? <View style={{ alignItems: "center", flexDirection: "row", gap: spacing.sm }}><ActivityIndicator color={palette.accent} /><Text style={styles.questionText}>Checking this question…</Text></View> : <Text style={styles.questionText}>{label}</Text>}
        </FocusablePressable>
      ))}
      {submitting ? <Text accessibilityLiveRegion="polite" style={styles.examinationStatus}>Checking the selected claim. Other questions are disabled until this request finishes.</Text> : null}
      {error ? (
        <View accessibilityLiveRegion="assertive" style={styles.examinationError}>
          <Text style={styles.examinationErrorTitle}>Could not complete the examination</Text>
          <Text style={styles.mutedText}>{error}</Text>
          <Text style={styles.mutedText}>No answer was saved. Choose a question to try again.</Text>
        </View>
      ) : null}
      {result ? (
        <View accessibilityLiveRegion="polite" style={[styles.answerCard, { backgroundColor: colors.surface.raised, borderColor: colors.border.subtle, borderWidth: 1 }]}>
          <Text style={styles.cardLabel}>ANSWER · {questionLabel(result.question_type)}</Text>
          <Text style={styles.answerText}>{result.answer}</Text>
          <Text style={styles.safeNote}>{result.disclaimer}</Text>
          <SectionHeader title="Evidence referenced in this answer" meta={`${result.evidence.length} item(s)`} />
          {result.evidence.length ? result.evidence.map((item) => <ExaminationEvidence key={item.id} item={item} />) : (
            <Text style={styles.mutedText}>No additional evidence was returned for this answer.</Text>
          )}
        </View>
      ) : null}
    </ScrollView>
  );
}

function ExaminationEvidence({ item }: { item: EvidenceItem }) {
  const detail = presentEvidence(item);
  const [linkFeedback, setLinkFeedback] = useState("");

  const openSource = async () => {
    if (!isSafeEvidenceDestination(item.url)) {
      setLinkFeedback("This source link cannot be opened safely. The cited URL is unavailable or uses an unsupported address.");
      return;
    }
    try {
      const canOpen = await Linking.canOpenURL(item.url);
      if (!canOpen) throw new Error("Unsupported source URL");
      await Linking.openURL(item.url);
      setLinkFeedback("");
    } catch {
      setLinkFeedback("Unable to open this cited source. Your examination answer remains unchanged; try the source again later.");
    }
  };

  return (
    <View style={styles.examinationEvidence}>
      <Text style={styles.evidenceTag}>{item.id} · {item.source_type}</Text>
      <Text style={styles.sourceText}>Source · {detail.source}</Text>
      <Text style={styles.sourceText}>Published · {detail.date}</Text>
      <Text style={[
        styles.freshnessText,
        detail.tone === "current" && styles.freshnessCurrent,
          detail.tone === "stale" && styles.freshnessStale,
        ]}>Freshness · {detail.freshness}</Text>
      {item.url ? (
        <FocusablePressable
          accessibilityHint="Opens the cited source in the browser."
          accessibilityLabel={`Open source for evidence ${item.id}`}
          accessibilityRole="link"
          onPress={() => { void openSource(); }}
          style={[styles.evidenceLink, { borderColor: colors.border.subtle, borderRadius: radii.md, borderWidth: 1, minWidth: interaction.minTargetSize, paddingHorizontal: spacing.md }]}
        >
          <Text style={styles.evidenceLinkText}>Open cited source ↗</Text>
        </FocusablePressable>
      ) : <Text style={styles.evidenceLinkUnavailable}>Source link unavailable</Text>}
      {linkFeedback ? <Text accessibilityLiveRegion="polite" style={[styles.mutedText, { backgroundColor: colors.surface.subtle, borderColor: colors.border.subtle, borderRadius: radii.sm, borderWidth: 1, marginTop: spacing.sm, padding: spacing.sm }]}>{linkFeedback}</Text> : null}
    </View>
  );
}

function questionLabel(questionType: ExaminationResponse["question_type"]): string {
  return questions.find(([type]) => type === questionType)?.[1] ?? "Focused question";
}
