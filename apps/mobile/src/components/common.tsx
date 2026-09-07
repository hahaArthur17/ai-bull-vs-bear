import React, { useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { appStyles as styles, colors, interaction, palette } from "../theme";


export function SectionHeader({ title, meta }: { title: string; meta: string }) {
  return <View style={styles.sectionHeader}><Text accessibilityRole="header" style={styles.sectionTitle}>{title}</Text><Text style={styles.mutedText}>{meta}</Text></View>;
}

export function Metric({ label, value }: { label: string; value: string }) {
  return <View style={styles.metric}><Text style={styles.cardLabel}>{label}</Text><Text style={styles.metricValue}>{value}</Text></View>;
}

export function BackButton({ onPress }: { onPress: () => void }) {
  return <Pressable accessibilityHint="Returns to the previous research screen." accessibilityLabel="Go back" accessibilityRole="button" onPress={onPress} style={styles.backButton}><Text style={styles.backText}>← Back</Text></Pressable>;
}

export function LoadingView({ label, onBack }: { label: string; onBack: () => void }) {
  return <View style={styles.loading}><BackButton onPress={onBack} /><ActivityIndicator color={palette.accent} size="large" /><Text accessibilityLiveRegion="polite" style={styles.mutedText}>{label}</Text></View>;
}

export function FailureView({ message, onBack, onRetry }: { message: string; onBack: () => void; onRetry: () => void }) {
  return (
    <View style={styles.loading}>
      <BackButton onPress={onBack} />
      <View accessibilityLiveRegion="assertive" style={styles.errorCard}>
        <Text style={styles.errorText}>{message}</Text>
        <Pressable accessibilityLabel="Retry loading this screen" accessibilityRole="button" style={styles.smallButton} onPress={onRetry}><Text style={styles.smallButtonText}>Retry</Text></Pressable>
      </View>
    </View>
  );
}

export function NavButton({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  const [focused, setFocused] = useState(false);

  return (
    <Pressable
      accessibilityHint={`Opens the ${label} section.`}
      accessibilityLabel={label}
      accessibilityRole="tab"
      accessibilityState={{ selected: active }}
      onBlur={() => setFocused(false)}
      onFocus={() => setFocused(true)}
      onPress={onPress}
      style={[styles.navButton, focused && { borderColor: colors.action.focus, borderWidth: interaction.focusRingWidth }]}
    >
      <Text style={[styles.navLabel, active && styles.navLabelActive]}>{label}</Text>
    </Pressable>
  );
}
