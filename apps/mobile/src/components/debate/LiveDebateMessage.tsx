import React, { useState } from "react";
import { type DimensionValue, Linking, StyleSheet, Text, View } from "react-native";

import { FocusablePressable } from "../common";
import type { DebateDraft } from "../../debateStream";
import { getDebateMessagePlacement } from "../../debateChatView";
import { debateMessageSections } from "../../liveDebateView";
import { exactExplanationTerm } from "../../explanationView";
import { colors, interaction } from "../../theme";
import { isSafeEvidenceDestination, type DebateEvidenceView } from "../../evidencePresentation";
import type { DebateMessageRecord } from "../../types";

const roleColors = {
  bull: colors.agent.bull,
  bear: colors.agent.bear,
  user: colors.agent.user,
  judge: colors.agent.judge,
  system: colors.content.secondary,
} as const;

type CanonicalMessageProps = {
  record: DebateMessageRecord;
  bubbleWidth: DimensionValue;
  judgeWidth: DimensionValue;
  challengeEnabled: boolean;
  selected: boolean;
  onChallenge: () => void;
  onExplainTerm: (term: string) => void;
};

export function CanonicalDebateMessage({
  record,
  bubbleWidth,
  judgeWidth,
  challengeEnabled,
  selected,
  onChallenge,
  onExplainTerm,
}: CanonicalMessageProps) {
  const [factsExpanded, setFactsExpanded] = useState(false);
  const placement = getDebateMessagePlacement(record.message.role, record.message.round_number);
  const sections = debateMessageSections(record);
  const accent = roleColors[placement.kind];
  const isJudge = placement.kind === "judge";
  const showsEvidenceDisclosure = placement.kind !== "user" && placement.kind !== "system";
  const canTarget = challengeEnabled
    && record.message.role !== "user"
    && record.message.role !== "system"
    && record.message.role !== "explainer";
  const alignStyle = placement.alignment === "right"
    ? messageStyles.alignRight
    : placement.alignment === "center"
      ? messageStyles.alignCenter
      : messageStyles.alignLeft;

  return (
    <View style={[messageStyles.messageWrap, alignStyle, { width: isJudge ? judgeWidth : bubbleWidth }]}>
      <View style={[
        messageStyles.messageCard,
        { borderColor: accent },
        isJudge && messageStyles.judgeCard,
        selected && messageStyles.selectedMessage,
      ]}>
        <View style={messageStyles.messageHeader}>
          <View style={[messageStyles.roleMark, { backgroundColor: accent }]} />
          <Text style={[messageStyles.roleLabel, { color: accent }]}>{placement.label}</Text>
          <Text style={messageStyles.messageMeta}>
            R{record.message.round_number} · E{record.message.exchange_number} · #{record.message.sequence_number}
          </Text>
        </View>
        <Text selectable style={[messageStyles.messageText, isJudge && messageStyles.judgeText]}>
          {sections.argument}
        </Text>

        {sections.interpretation ? (
          <View style={messageStyles.reasoningSection}>
            <Text style={messageStyles.reasoningLabel}>INTERPRETATION</Text>
            <Text style={messageStyles.reasoningText}>{sections.interpretation}</Text>
          </View>
        ) : null}
        {sections.uncertainty ? (
          <View style={messageStyles.reasoningSection}>
            <Text style={messageStyles.reasoningLabel}>UNCERTAINTY</Text>
            <Text style={messageStyles.reasoningText}>{sections.uncertainty}</Text>
          </View>
        ) : null}

        {record.message.terms.length > 0 ? (
          <View style={messageStyles.termRow}>
            {record.message.terms.map((term) => (
              <FocusablePressable
                key={`${record.message.id}:${term}`}
                disabled={exactExplanationTerm(record, term) === null}
                onPress={() => onExplainTerm(term)}
                style={messageStyles.termChip}
                accessibilityRole="button"
                accessibilityLabel={`Explain ${term}`}
                accessibilityState={{ disabled: exactExplanationTerm(record, term) === null }}
              >
                <Text style={messageStyles.termText}>Explain “{term}”</Text>
              </FocusablePressable>
            ))}
          </View>
        ) : null}

        {showsEvidenceDisclosure ? (
          <>
            <FocusablePressable
              onPress={() => setFactsExpanded((current) => !current)}
              style={messageStyles.disclosureButton}
              accessibilityRole="button"
              accessibilityState={{ expanded: factsExpanded }}
              accessibilityLabel={`${factsExpanded ? "Hide" : "Show"} facts used by ${placement.label}`}
            >
              <Text style={messageStyles.disclosureText}>
                {factsExpanded ? "Hide facts" : `Facts & evidence (${sections.factsUsed.length})`}
              </Text>
              <Text style={messageStyles.disclosureIcon}>{factsExpanded ? "−" : "+"}</Text>
            </FocusablePressable>

            {factsExpanded ? (
              <View style={messageStyles.factList}>
                {!sections.hasAuthoritativePresentation ? (
                  <Text style={messageStyles.factUnavailable}>
                    This retained message predates the authoritative fact presentation. No facts are inferred from citation IDs.
                  </Text>
                ) : sections.factsUsed.length === 0 ? (
                  <Text style={messageStyles.factUnavailable}>No cited facts were recorded for this message.</Text>
                ) : sections.factsUsed.map((fact) => (
                  <DebateFact key={`${record.message.id}:${fact.evidenceId}`} fact={fact} />
                ))}
              </View>
            ) : null}
          </>
        ) : null}

        {canTarget ? (
          <FocusablePressable
            onPress={onChallenge}
            style={messageStyles.messageAction}
            accessibilityLabel={selected ? "Selected for Round 2 challenge" : "Challenge this point in Round 2"}
            accessibilityRole="button"
            accessibilityState={{ selected }}
          >
            <Text style={messageStyles.messageActionText}>
              {selected ? "Selected for Round 2" : "Challenge this point →"}
            </Text>
          </FocusablePressable>
        ) : null}
      </View>
    </View>
  );
}

function DebateFact({ fact }: { fact: DebateEvidenceView }) {
  const [sourceError, setSourceError] = useState(false);
  const sourceAvailable = isSafeEvidenceDestination(fact.sourceDestination);
  const openSource = () => {
    const sourceDestination = fact.sourceDestination;
    if (!sourceDestination) return;
    setSourceError(false);
    void Linking.openURL(sourceDestination).catch(() => setSourceError(true));
  };
  return (
    <View style={messageStyles.factCard}>
      <View style={messageStyles.factHeader}>
        <Text style={messageStyles.factId}>{fact.evidenceId}</Text>
        <Text style={messageStyles.factType}>{fact.evidenceType ?? "TYPE UNAVAILABLE"}</Text>
      </View>
      <Text style={messageStyles.factTitle}>{fact.title ?? "Title unavailable"}</Text>
      <Text style={messageStyles.factText}>{fact.fact ?? "Fact text unavailable"}</Text>
      {fact.supportSpan ? <Text style={messageStyles.supportSpan}>Support · {fact.supportSpan}</Text> : null}
      <Text style={messageStyles.factMeta}>{fact.source} · {fact.date}</Text>
      <Text style={messageStyles.factMeta}>{fact.freshness}</Text>
      {fact.missingMetadata.length > 0 ? (
        <Text style={messageStyles.missingMetadata}>
          Missing metadata · {fact.missingMetadata.map(humanizeMetadataName).join(", ")}
        </Text>
      ) : null}
      {sourceAvailable ? (
        <FocusablePressable
          onPress={openSource}
          style={messageStyles.sourceLink}
          accessibilityRole="link"
          accessibilityLabel={`Open source for ${fact.evidenceId}`}
        >
          <Text style={messageStyles.sourceLinkText}>Open cited source ↗</Text>
        </FocusablePressable>
      ) : (
        <Text style={messageStyles.sourceUnavailable}>Source link unavailable</Text>
      )}
      {sourceError ? (
        <Text accessibilityLiveRegion="polite" style={messageStyles.sourceError}>
          This source could not be opened on this device.
        </Text>
      ) : null}
    </View>
  );
}

function humanizeMetadataName(value: string): string {
  return value.replace(/_/g, " ");
}

export function DraftDebateMessage({
  draft,
  roundNumber,
  bubbleWidth,
  judgeWidth,
}: {
  draft: DebateDraft;
  roundNumber: number;
  bubbleWidth: DimensionValue;
  judgeWidth: DimensionValue;
}) {
  const placement = getDebateMessagePlacement(draft.role, roundNumber);
  const accent = roleColors[placement.kind];
  const alignStyle = placement.alignment === "right"
    ? messageStyles.alignRight
    : placement.alignment === "center"
      ? messageStyles.alignCenter
      : messageStyles.alignLeft;
  return (
    <View
      accessibilityLabel={`${placement.label} streaming draft. Temporary output, not yet canonical.`}
      accessibilityLiveRegion="polite"
      style={[
        messageStyles.messageWrap,
        alignStyle,
        { width: placement.kind === "judge" ? judgeWidth : bubbleWidth },
      ]}
    >
      <View style={[messageStyles.messageCard, messageStyles.draftCard, { borderColor: accent }]}>
        <View style={messageStyles.messageHeader}>
          <View style={[messageStyles.roleMark, { backgroundColor: accent }]} />
          <Text style={[messageStyles.roleLabel, { color: accent }]}>{placement.label}</Text>
          <Text style={messageStyles.streamingText}>● STREAMING DRAFT</Text>
        </View>
        <Text style={messageStyles.messageText}>{draft.content || "The agent has started this turn…"}</Text>
        <Text style={messageStyles.draftNote}>Temporary output · not yet canonical</Text>
      </View>
    </View>
  );
}

const messageStyles = StyleSheet.create({
  messageWrap: { marginBottom: 12 },
  alignLeft: { alignSelf: "flex-start" },
  alignRight: { alignSelf: "flex-end" },
  alignCenter: { alignSelf: "center" },
  messageCard: { backgroundColor: colors.surface.raised, borderWidth: 1, borderRadius: 18, padding: 15 },
  judgeCard: { backgroundColor: colors.surface.warning, borderWidth: 1.5 },
  selectedMessage: { backgroundColor: colors.surface.selected, borderWidth: 2 },
  messageHeader: { flexDirection: "row", alignItems: "center", flexWrap: "wrap", gap: 7 },
  roleMark: { width: 8, height: 8, borderRadius: 4 },
  roleLabel: { flexGrow: 1, fontSize: 11, fontWeight: "900", letterSpacing: 0.8, textTransform: "uppercase" },
  messageMeta: { color: colors.content.secondary, fontSize: 9, fontWeight: "700" },
  messageText: { color: colors.content.primary, fontSize: 14, lineHeight: 22, marginTop: 11 },
  judgeText: { fontSize: 15, lineHeight: 23, fontWeight: "700" },
  reasoningSection: { borderTopColor: colors.border.subtle, borderTopWidth: 1, marginTop: 12, paddingTop: 10 },
  reasoningLabel: { color: colors.content.secondary, fontSize: 9, fontWeight: "900", letterSpacing: 0.9 },
  reasoningText: { color: colors.content.primary, fontSize: 12, lineHeight: 19, marginTop: 5 },
  termRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 12 },
  termChip: { alignItems: "center", borderColor: colors.border.subtle, borderWidth: 1, borderRadius: 12, justifyContent: "center", minHeight: interaction.minTargetSize, minWidth: interaction.minTargetSize, paddingHorizontal: 10, paddingVertical: 6 },
  termText: { color: colors.content.secondary, fontSize: 10 },
  disclosureButton: { minHeight: interaction.minTargetSize, flexDirection: "row", alignItems: "center", justifyContent: "space-between", borderTopColor: colors.border.subtle, borderTopWidth: 1, marginTop: 12, paddingTop: 10 },
  disclosureText: { color: colors.action.primary, fontSize: 11, fontWeight: "900" },
  disclosureIcon: { color: colors.action.primary, fontSize: 18, fontWeight: "700" },
  factList: { gap: 8, marginTop: 4 },
  factCard: { backgroundColor: colors.surface.subtle, borderColor: colors.border.subtle, borderWidth: 1, borderRadius: 12, padding: 12 },
  factHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
  factId: { color: colors.action.primary, fontSize: 10, fontWeight: "900", letterSpacing: 0.7 },
  factType: { color: colors.content.secondary, fontSize: 9, fontWeight: "800", textTransform: "uppercase" },
  factTitle: { color: colors.content.primary, fontSize: 12, fontWeight: "800", marginTop: 8 },
  factText: { color: colors.content.primary, fontSize: 12, lineHeight: 18, marginTop: 6 },
  supportSpan: { color: colors.content.secondary, fontSize: 10, lineHeight: 16, marginTop: 7 },
  factMeta: { color: colors.content.secondary, fontSize: 10, lineHeight: 15, marginTop: 5 },
  missingMetadata: { color: colors.content.warning, fontSize: 10, lineHeight: 15, marginTop: 7 },
  sourceLink: { alignSelf: "flex-start", justifyContent: "center", minHeight: interaction.minTargetSize, minWidth: interaction.minTargetSize, marginTop: 7, paddingHorizontal: 2 },
  sourceLinkText: { color: colors.action.secondary, fontSize: 11, fontWeight: "800" },
  sourceUnavailable: { color: colors.content.secondary, fontSize: 10, marginTop: 9 },
  sourceError: { color: colors.content.danger, fontSize: 10, lineHeight: 15, marginTop: 2 },
  factUnavailable: { color: colors.content.secondary, fontSize: 11, lineHeight: 17, paddingVertical: 8 },
  messageAction: { alignSelf: "flex-start", alignItems: "center", justifyContent: "center", marginTop: 8, minHeight: interaction.minTargetSize, minWidth: interaction.minTargetSize, paddingHorizontal: 2 },
  messageActionText: { color: colors.agent.user, fontSize: 12, fontWeight: "800" },
  draftCard: { backgroundColor: colors.surface.elevated, borderStyle: "dashed" },
  streamingText: { color: colors.agent.user, fontSize: 9, fontWeight: "900", letterSpacing: 0.7 },
  draftNote: { color: colors.content.secondary, fontSize: 10, fontStyle: "italic", marginTop: 9 },
});
