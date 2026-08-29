import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";

import { BackButton, LoadingView, SectionHeader } from "../components/common";
import { appStyles as styles, palette } from "../theme";
import type { Claim, ExaminationResponse } from "../types";

type ExaminationScreenProps = {
  claim: Claim | null;
  result: ExaminationResponse | null;
  loading: boolean;
  onBack: () => void;
  onAsk: (questionType: ExaminationResponse["question_type"]) => void;
};

const questions: ReadonlyArray<readonly [ExaminationResponse["question_type"], string]> = [
  ["evidence_support", "What evidence supports this?"],
  ["explain_term", "What does this term mean?"],
  ["signal_strength", "How strong is the signal?"],
  ["risk_meaning", "What is the risk meaning?"],
];

export function ExaminationScreen({ claim, result, loading, onBack, onAsk }: ExaminationScreenProps) {
  if (!claim) return <LoadingView label="No claim selected." onBack={onBack} />;
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <BackButton onPress={onBack} />
      <Text style={styles.eyebrow}>SELECTED {claim.agent.toUpperCase()} CLAIM</Text>
      <Text style={styles.detailTitle}>Cross Examination</Text>
      <View style={styles.answerCard}><Text style={styles.cardTitle}>{claim.text}</Text><Text style={styles.evidenceIds}>{claim.evidence_ids.join(" + ")}</Text></View>
      <SectionHeader title="Ask a focused question" meta="explanation agent" />
      {questions.map(([type, label]) => (
        <Pressable key={type} style={styles.questionButton} onPress={() => onAsk(type)}><Text style={styles.questionText}>{label}</Text></Pressable>
      ))}
      {loading ? <ActivityIndicator color={palette.accent} style={styles.loader} /> : null}
      {result ? <View style={styles.answerCard}><Text style={styles.cardLabel}>ANSWER</Text><Text style={styles.answerText}>{result.answer}</Text><Text style={styles.safeNote}>{result.disclaimer}</Text></View> : null}
    </ScrollView>
  );
}
