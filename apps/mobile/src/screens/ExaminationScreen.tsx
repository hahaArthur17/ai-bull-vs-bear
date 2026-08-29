import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";

import { BackButton, LoadingView, SectionHeader } from "../components/common";
import { presentEvidence } from "../evidencePresentation";
import { appStyles as styles, palette } from "../theme";
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
    <ScrollView contentContainerStyle={styles.page}>
      <BackButton onPress={onBack} />
      <Text style={styles.eyebrow}>SELECTED {claim.agent.toUpperCase()} CLAIM</Text>
      <Text style={styles.detailTitle}>Cross Examination</Text>
      <View style={styles.answerCard}><Text style={styles.cardTitle}>{claim.text}</Text><Text style={styles.evidenceIds}>{claim.evidence_ids.join(" + ")}</Text></View>
      <SectionHeader title="Ask a focused question" meta="explanation agent" />
      {questions.map(([type, label]) => (
        <Pressable
          key={type}
          accessibilityHint="Requests an explanation of the selected claim without changing the Debate."
          accessibilityRole="button"
          accessibilityState={{ busy: pendingQuestion === type, disabled: submitting }}
          disabled={submitting}
          style={[styles.questionButton, submitting && styles.questionButtonDisabled]}
          onPress={() => onAsk(type)}
        >
          {pendingQuestion === type ? <ActivityIndicator color={palette.accent} /> : <Text style={styles.questionText}>{label}</Text>}
        </Pressable>
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
        <View accessibilityLiveRegion="polite" style={styles.answerCard}>
          <Text style={styles.cardLabel}>ANSWER</Text>
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
    </View>
  );
}
