import React, { useState } from "react";
import type { ComponentProps } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { appStyles as styles, palette } from "../theme";
import { focusablePressableStyle } from "../focusablePressable";

type FocusablePressableProps = ComponentProps<typeof Pressable>;

/**
 * Keeps React Native press behavior intact while guaranteeing an app-owned,
 * high-contrast focus ring for keyboard users on Web.
 */
export function FocusablePressable({
  disabled,
  onBlur,
  onFocus,
  style,
  ...props
}: FocusablePressableProps) {
  const [focused, setFocused] = useState(false);
  return (
    <Pressable
      {...props}
      disabled={disabled}
      onBlur={(event) => {
        setFocused(false);
        onBlur?.(event);
      }}
      onFocus={(event) => {
        setFocused(true);
        onFocus?.(event);
      }}
      style={(state) => [
        typeof style === "function" ? style(state) : style,
        focusablePressableStyle(focused, disabled ?? false),
      ]}
    />
  );
}


export function SectionHeader({ title, meta }: { title: string; meta?: string }) {
  return (
    <View style={styles.sectionHeader}>
      <Text accessibilityRole="header" style={styles.sectionTitle}>{title}</Text>
      {meta ? <Text style={styles.sectionMeta}>{meta}</Text> : null}
    </View>
  );
}

export function Metric({ label, value }: { label: string; value: string }) {
  return <View style={styles.metric}><Text style={styles.cardLabel}>{label}</Text><Text style={styles.metricValue}>{value}</Text></View>;
}

export function BackButton({ onPress }: { onPress: () => void }) {
  return <FocusablePressable accessibilityHint="Returns to the previous research screen." accessibilityLabel="Go back" accessibilityRole="button" onPress={onPress} style={styles.backButton}><Text style={styles.backText}>← Back</Text></FocusablePressable>;
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
        <FocusablePressable accessibilityLabel="Retry loading this screen" accessibilityRole="button" style={styles.smallButton} onPress={onRetry}><Text style={styles.smallButtonText}>Retry</Text></FocusablePressable>
      </View>
    </View>
  );
}

export function NavButton({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <FocusablePressable
      accessibilityHint={`Opens the ${label} section.`}
      accessibilityLabel={label}
      accessibilityRole="tab"
      accessibilityState={{ selected: active }}
      onPress={onPress}
      style={styles.navButton}
    >
      <Text style={[styles.navLabel, active && styles.navLabelActive]}>{label}</Text>
    </FocusablePressable>
  );
}
