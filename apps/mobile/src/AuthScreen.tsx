import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { supabase } from "./supabase";
import { colors, interaction, palette, radii, spacing, typography } from "./theme";
import { isAuthenticationButtonSubmitting } from "./authState";
import type { AuthenticationMode } from "./authState";

function validEmail(value: string): boolean {
  return /^\S+@\S+\.\S+$/.test(value);
}

export function AuthScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submittingMode, setSubmittingMode] = useState<AuthenticationMode | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const normalizedEmail = email.trim();
  const isEmailValid = validEmail(normalizedEmail);
  const isPasswordValid = password.length >= 6;
  const isSubmitting = submittingMode !== null;
  const canSubmit = !isSubmitting && isEmailValid && isPasswordValid;

  const authenticate = async (mode: AuthenticationMode) => {
    if (!supabase || !canSubmit) return;
    setSubmittingMode(mode);
    setError("");
    setMessage("");
    try {
      const result = mode === "sign-in"
        ? await supabase.auth.signInWithPassword({ email: normalizedEmail, password })
        : await supabase.auth.signUp({ email: normalizedEmail, password });
      if (result.error) {
        setError(result.error.message);
      } else if (mode === "sign-up" && !result.data.session) {
        setMessage("Account created. Check your email to confirm it, then return here to sign in.");
      }
    } catch {
      setError("We could not complete that request. Check your connection and try again.");
    } finally {
      setSubmittingMode(null);
    }
  };

  const formHint = !normalizedEmail
    ? "Enter your email to continue."
    : !isEmailValid
      ? "Enter a valid email address."
      : !isPasswordValid
        ? "Use at least six password characters."
        : "Your credentials are ready to submit.";

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
        <View style={styles.brandRow} accessibilityRole="header">
          <View style={styles.brandMark}><Text style={styles.brandMarkText}>B/B</Text></View>
          <View><Text style={styles.brandName}>AI BULL VS BEAR</Text><Text style={styles.brandMeta}>RESEARCH WORKSPACE</Text></View>
        </View>
        <View style={styles.card}>
          <Text style={styles.eyebrow}>PRIVATE RESEARCH ACCESS</Text>
          <Text style={styles.title}>Make your next market question traceable.</Text>
          <Text style={styles.body}>
            Sign in to keep your watchlist, research history, and Debate sessions scoped to your account.
          </Text>
          <View style={styles.divider} />
          <View style={styles.fieldGroup}>
            <Text nativeID="auth-email-label" style={styles.label}>EMAIL ADDRESS</Text>
            <TextInput
              accessibilityLabel="Email address"
              autoCapitalize="none"
              autoComplete="email"
              keyboardType="email-address"
              onChangeText={setEmail}
              placeholder="you@example.com"
              placeholderTextColor={palette.muted}
              style={styles.input}
              textContentType="emailAddress"
              value={email}
            />
          </View>
          <View style={styles.fieldGroup}>
            <Text nativeID="auth-password-label" style={styles.label}>PASSWORD</Text>
            <TextInput
              accessibilityLabel="Password"
              autoCapitalize="none"
              autoComplete="password"
              onChangeText={setPassword}
              placeholder="At least 6 characters"
              placeholderTextColor={palette.muted}
              secureTextEntry
              style={styles.input}
              textContentType="password"
              value={password}
            />
          </View>
          <Text accessibilityLiveRegion="polite" style={styles.formHint}>{formHint}</Text>
          {error ? <Text accessibilityLiveRegion="assertive" style={styles.error}>{error}</Text> : null}
          {message ? <Text accessibilityLiveRegion="polite" style={styles.message}>{message}</Text> : null}
          <Pressable
            accessibilityHint="Signs in with the email address and password above."
            accessibilityRole="button"
            accessibilityState={{ disabled: !canSubmit, busy: isAuthenticationButtonSubmitting(submittingMode, "sign-in") }}
            disabled={!canSubmit}
            onPress={() => void authenticate("sign-in")}
            style={[styles.primaryButton, !canSubmit && styles.buttonDisabled]}
          >
            {isAuthenticationButtonSubmitting(submittingMode, "sign-in") ? <ActivityIndicator color={colors.content.onSignal} /> : <Text style={styles.primaryText}>Sign in to workspace</Text>}
          </Pressable>
          <Pressable
            accessibilityHint="Creates an account with the email address and password above."
            accessibilityRole="button"
            accessibilityState={{ disabled: !canSubmit, busy: isAuthenticationButtonSubmitting(submittingMode, "sign-up") }}
            disabled={!canSubmit}
            onPress={() => void authenticate("sign-up")}
            style={[styles.secondaryButton, !canSubmit && styles.secondaryButtonDisabled]}
          >
            {isAuthenticationButtonSubmitting(submittingMode, "sign-up") ? <ActivityIndicator color={palette.accent} /> : <Text style={[styles.secondaryText, !canSubmit && styles.secondaryTextDisabled]}>Create an account</Text>}
          </Pressable>
          <Text style={styles.note}>
            Authentication is handled by Supabase. Never paste passwords, API keys, or tokens into a research prompt.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: palette.paper },
  scrollContent: { alignItems: "center", flexGrow: 1, justifyContent: "center", padding: spacing.xl, gap: spacing.lg },
  brandRow: { alignItems: "center", alignSelf: "center", flexDirection: "row", gap: spacing.sm, maxWidth: 640, width: "100%" },
  brandMark: { alignItems: "center", backgroundColor: palette.accent, borderRadius: radii.md, height: interaction.minTargetSize, justifyContent: "center", width: interaction.minTargetSize },
  brandMarkText: { color: colors.content.inverse, fontSize: 11, fontWeight: "900", letterSpacing: 0.4 },
  brandName: { color: palette.ink, fontSize: 12, fontWeight: "900", letterSpacing: 1.1 },
  brandMeta: { color: palette.muted, fontSize: 10, fontWeight: "800", letterSpacing: 0.8, marginTop: 2 },
  card: { alignSelf: "center", backgroundColor: palette.card, borderColor: palette.line, borderRadius: radii.xl, borderWidth: 1, maxWidth: 640, padding: spacing.xl, width: "100%" },
  eyebrow: { color: palette.signal, fontSize: typography.label.fontSize, fontWeight: typography.label.fontWeight, letterSpacing: typography.label.letterSpacing, marginBottom: spacing.sm },
  title: { color: palette.ink, fontSize: typography.pageTitle.fontSize, fontWeight: typography.pageTitle.fontWeight, lineHeight: typography.pageTitle.lineHeight, marginBottom: spacing.sm },
  body: { color: palette.muted, fontSize: 15, lineHeight: 23 },
  divider: { backgroundColor: palette.line, height: 1, marginVertical: spacing.lg },
  fieldGroup: { marginBottom: spacing.md },
  label: { color: palette.ink, fontSize: 11, fontWeight: "800", letterSpacing: 0.8, marginBottom: spacing.xs },
  input: { borderColor: palette.line, borderRadius: radii.md, borderWidth: 1, color: palette.ink, fontSize: 16, minHeight: interaction.minTargetSize, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  formHint: { color: palette.muted, fontSize: 12, lineHeight: 18, marginBottom: spacing.md },
  error: { backgroundColor: colors.surface.danger, borderRadius: radii.sm, color: colors.content.danger, fontSize: 12, lineHeight: 18, marginBottom: spacing.md, padding: spacing.sm },
  message: { backgroundColor: colors.surface.positive, borderRadius: radii.sm, color: palette.accent, fontSize: 12, lineHeight: 18, marginBottom: spacing.md, padding: spacing.sm },
  primaryButton: { alignItems: "center", backgroundColor: palette.signal, borderRadius: radii.md, justifyContent: "center", minHeight: interaction.minTargetSize, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  primaryText: { color: colors.content.onSignal, fontSize: 14, fontWeight: "800" },
  buttonDisabled: { opacity: 0.45 },
  secondaryButton: { alignItems: "center", borderColor: palette.accent, borderRadius: radii.md, borderWidth: 1, justifyContent: "center", marginTop: spacing.sm, minHeight: interaction.minTargetSize, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  secondaryButtonDisabled: { borderColor: palette.line },
  secondaryText: { color: palette.accent, fontSize: 14, fontWeight: "800" },
  secondaryTextDisabled: { color: palette.muted },
  note: { color: palette.muted, fontSize: 11, lineHeight: 17, marginTop: spacing.lg },
});
