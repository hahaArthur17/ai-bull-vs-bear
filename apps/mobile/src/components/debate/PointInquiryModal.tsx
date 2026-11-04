import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import type { DebateDraft } from "../../debateStream";
import type { PointInquiryMode } from "../../pointInquiryView";
import { canDismissPointInquiry, canPrepareRoundTwoChallenge } from "../../pointInquiryView";
import type { DebateMessageRecord, ExplanationResult } from "../../types";
import { FocusablePressable } from "../common";
import { colors, screenStyles } from "./debateStyles";

function rolePresentation(
  role: DebateMessageRecord["message"]["role"] | DebateDraft["role"],
  isFinalJudge = false,
) {
  if (role === "bull") return { label: "BULL", color: colors.bull };
  if (role === "bear") return { label: "BEAR", color: colors.bear };
  if (role === "judge") {
    return {
      label: isFinalJudge ? "FINAL NEUTRAL JUDGE" : "INTERIM NEUTRAL JUDGE",
      color: colors.judge,
    };
  }
  if (role === "user") return { label: "YOUR QUESTION", color: colors.cyan };
  if (role === "explainer") return { label: "EXPLAINER", color: colors.warning };
  return { label: "SYSTEM", color: colors.muted };
}

type PointInquiryProps = {
  target: DebateMessageRecord;
  mode: PointInquiryMode;
  selectedText: string;
  question: string;
  selectedTextIsValid: boolean;
  canChallenge: boolean;
  canSubmitExplanation: boolean;
  canSubmitChallenge: boolean;
  explaining: boolean;
  challenging: boolean;
  explanationResult: ExplanationResult | null;
  explanationError: string;
  actionError: string;
  onClose: () => void;
  onSelectedTextChange: (value: string) => void;
  onQuestionChange: (value: string) => void;
  onExplain: () => void;
  onPrepareChallenge: () => void;
  onReturnToExplanation: () => void;
  onSubmitChallenge: () => void;
};

/** The modal owns dismissal; each content section has one display responsibility. */
export function PointInquiryModal(props: PointInquiryProps) {
  const { mode, challenging, onClose } = props;
  const isChallengeConfirmation = mode === "challenge";
  const canDismiss = canDismissPointInquiry(challenging);
  return (
    <Modal
      animationType="fade"
      onRequestClose={() => {
        if (canDismiss) onClose();
      }}
      presentationStyle="overFullScreen"
      statusBarTranslucent
      transparent
      visible
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={screenStyles.modalRoot}
      >
        <Pressable
          accessible={false}
          disabled={!canDismiss}
          onPress={onClose}
          style={screenStyles.modalBackdrop}
        />
        <View
          accessibilityLabel={
            isChallengeConfirmation ? "Confirm Round 2 challenge" : "Ask about this Debate point"
          }
          accessibilityViewIsModal
          style={screenStyles.modalCard}
        >
          <ScrollView
            style={screenStyles.modalScroll}
            contentContainerStyle={screenStyles.modalContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            <PointInquiryHeader {...props} />
            <PointInquiryFields {...props} />
            <PointInquiryActions {...props} />
            <ExplanationAnswer {...props} />
            <FocusablePressable
              disabled={!canDismiss}
              style={[screenStyles.modalCancelButton, !canDismiss && screenStyles.disabledButton]}
              onPress={onClose}
              accessibilityLabel="Cancel and close this dialog"
              accessibilityRole="button"
              accessibilityState={{ disabled: !canDismiss }}
            >
              <Text style={screenStyles.modalCancelText}>Cancel</Text>
            </FocusablePressable>
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

function PointInquiryHeader({ mode, target, challenging, onClose }: PointInquiryProps) {
  const isChallengeConfirmation = mode === "challenge";
  const isInterruptedPrefix = !target.message.is_complete;
  const canDismiss = canDismissPointInquiry(challenging);
  return (
    <>
      <View style={screenStyles.rowBetween}>
        <Text
          style={[
            screenStyles.modalEyebrow,
            {
              color: isChallengeConfirmation ? colors.judge : colors.bull,
            },
          ]}
        >
          {isChallengeConfirmation
            ? "ROUND 2 · EXPLICIT CONFIRMATION"
            : "EDUCATIONAL EXPLAINER · READ ONLY"}
        </Text>
        <FocusablePressable
          disabled={!canDismiss}
          onPress={onClose}
          style={[screenStyles.modalCloseButton, !canDismiss && screenStyles.disabledButton]}
          accessibilityRole="button"
          accessibilityLabel="Close this point dialog"
          accessibilityState={{ disabled: !canDismiss }}
        >
          <Text style={screenStyles.modalCloseText}>Close ×</Text>
        </FocusablePressable>
      </View>
      <Text style={screenStyles.modalTitle}>
        {isChallengeConfirmation
          ? "Start a second debate round?"
          : isInterruptedPrefix
            ? "Ask about the stopped text"
            : "Ask before you challenge"}
      </Text>
      <Text style={screenStyles.modalHelp}>
        {isChallengeConfirmation
          ? "This will commit your exact question and start Round 2. It is a Debate intervention, not an explanation."
          : isInterruptedPrefix
            ? "Ask the Explainer about an exact passage in the frozen prefix. The response treats it as unfinished, has no unverified citations, and does not resume or change the Debate."
            : "Ask about this passage. Check linked excerpts for factual claims. The answer does not change the Debate."}
      </Text>
    </>
  );
}

function PointInquiryFields({
  mode,
  target,
  selectedText,
  question,
  selectedTextIsValid,
  challenging,
  explanationError,
  actionError,
  onSelectedTextChange,
  onQuestionChange,
}: PointInquiryProps) {
  const isChallengeConfirmation = mode === "challenge";
  const isInterruptedPrefix = !target.message.is_complete;
  return (
    <>
      <Text style={screenStyles.inputLabel}>
        EXACT PASSAGE · {rolePresentation(target.message.role).label}
      </Text>
      <TextInput
        value={selectedText}
        editable={!challenging}
        onChangeText={onSelectedTextChange}
        maxLength={500}
        multiline
        style={screenStyles.pointPassageInput}
        placeholder="Keep an exact passage from this message"
        placeholderTextColor={colors.muted}
        accessibilityLabel="Exact passage from the selected Debate message"
        accessibilityHint={
          isInterruptedPrefix
            ? "Edit this only to another exact passage from the same frozen prefix."
            : "Edit this only to another exact passage from the same completed message."
        }
      />
      {!selectedTextIsValid ? (
        <Text style={screenStyles.validationText}>
          Keep an exact passage that occurs in the selected message.
        </Text>
      ) : null}

      <Text style={screenStyles.inputLabel}>YOUR QUESTION</Text>
      <TextInput
        autoFocus
        value={question}
        editable={!challenging}
        onChangeText={onQuestionChange}
        maxLength={500}
        multiline
        style={screenStyles.textArea}
        placeholder={
          isChallengeConfirmation
            ? "What should both sides reconsider in Round 2?"
            : "What is unclear, or what would you like explained?"
        }
        placeholderTextColor={colors.muted}
        accessibilityLabel={
          isChallengeConfirmation
            ? "Question proposed for Round 2"
            : "Educational question about the selected point"
        }
      />

      {explanationError && !isChallengeConfirmation ? (
        <Text accessibilityLiveRegion="assertive" style={screenStyles.validationText}>
          {explanationError}
        </Text>
      ) : null}
      {actionError && isChallengeConfirmation ? (
        <Text accessibilityLiveRegion="assertive" style={screenStyles.validationText}>
          {actionError}
        </Text>
      ) : null}
    </>
  );
}

function PointInquiryActions({
  mode,
  canChallenge,
  selectedTextIsValid,
  question,
  explaining,
  canSubmitChallenge,
  challenging,
  canSubmitExplanation,
  onSubmitChallenge,
  onReturnToExplanation,
  onExplain,
  onPrepareChallenge,
}: PointInquiryProps) {
  const isChallengeConfirmation = mode === "challenge";
  const canPrepareChallenge = canPrepareRoundTwoChallenge({
    canChallenge,
    selectedTextIsValid,
    question,
    explaining,
  });
  return (
    <>
      {isChallengeConfirmation ? (
        <>
          <FocusablePressable
            disabled={!canSubmitChallenge || challenging}
            style={[
              screenStyles.challengeButton,
              !canSubmitChallenge && screenStyles.disabledButton,
            ]}
            onPress={onSubmitChallenge}
            accessibilityLabel="Confirm and start Round 2 with this challenge"
            accessibilityRole="button"
            accessibilityState={{
              busy: challenging,
              disabled: !canSubmitChallenge,
            }}
          >
            {challenging ? <ActivityIndicator color={colors.background} size="small" /> : null}
            <Text style={screenStyles.challengeButtonText}>
              {challenging ? "Starting Round 2…" : "Start Round 2 with this challenge"}
            </Text>
          </FocusablePressable>
          <FocusablePressable
            disabled={challenging}
            style={[screenStyles.modalSecondaryButton, challenging && screenStyles.disabledButton]}
            onPress={onReturnToExplanation}
            accessibilityLabel="Return to educational explanation"
            accessibilityRole="button"
            accessibilityState={{ disabled: challenging }}
          >
            <Text style={screenStyles.modalSecondaryText}>← Back to explanation</Text>
          </FocusablePressable>
        </>
      ) : (
        <>
          <FocusablePressable
            disabled={!canSubmitExplanation}
            style={[
              screenStyles.explanationButton,
              !canSubmitExplanation && screenStyles.disabledButton,
            ]}
            onPress={onExplain}
            accessibilityLabel="Ask the educational Explainer"
            accessibilityRole="button"
            accessibilityState={{
              busy: explaining,
              disabled: !canSubmitExplanation,
            }}
          >
            {explaining ? <ActivityIndicator color={colors.background} size="small" /> : null}
            <Text style={screenStyles.explanationButtonText}>
              {explaining ? "Asking Explainer…" : "Ask Explainer"}
            </Text>
          </FocusablePressable>
          {canChallenge ? (
            <FocusablePressable
              disabled={!canPrepareChallenge}
              style={[
                screenStyles.modalSecondaryButton,
                !canPrepareChallenge && screenStyles.disabledButton,
              ]}
              onPress={onPrepareChallenge}
              accessibilityLabel="Prepare this question as a Round 2 challenge"
              accessibilityRole="button"
              accessibilityState={{ disabled: !canPrepareChallenge }}
            >
              <Text style={screenStyles.modalSecondaryText}>Prepare a Round 2 challenge →</Text>
            </FocusablePressable>
          ) : null}
        </>
      )}
    </>
  );
}

function ExplanationAnswer({ mode, explanationResult }: PointInquiryProps) {
  const isChallengeConfirmation = mode === "challenge";
  return (
    <>
      {explanationResult && !isChallengeConfirmation ? (
        <View accessibilityLiveRegion="polite" style={screenStyles.explanationResult}>
          <Text style={screenStyles.explanationResultTitle}>EXPLAINER ANSWER</Text>
          <Text style={screenStyles.explanationContent}>{explanationResult.content}</Text>
          {explanationResult.evidence_ids.length > 0 ? (
            <Text style={screenStyles.citations}>
              EVIDENCE {explanationResult.evidence_ids.join(" · ")}
            </Text>
          ) : null}
          {explanationResult.guardrail_status === "rewritten" ? (
            <Text style={screenStyles.explanationSafetyNote}>
              Safety language was adjusted to keep this educational.
            </Text>
          ) : null}
        </View>
      ) : null}
    </>
  );
}
