import React, { useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import { appStyles as styles } from "../theme";


export function AboutScreen({ onSignOut }: { onSignOut?: () => void }) {
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text style={styles.eyebrow}>ABOUT THIS RESEARCH DEMO</Text>
      <Text style={styles.detailTitle}>AI Bull vs Bear</Text>
      <Text style={styles.heroBody}>An educational research workspace that puts technical signals, filing and news evidence, and competing Bull and Bear arguments side by side.</Text>
      <View style={styles.aboutCard}>
        <Text accessibilityRole="header" style={styles.cardTitle}>Start with the evidence</Text>
        <Text style={styles.mutedText}>Every research view identifies its source, date, and freshness. Missing or stale inputs are shown as limits, not filled with invented certainty.</Text>
      </View>
      <View style={styles.aboutCard}>
        <Text accessibilityRole="header" style={styles.cardTitle}>A structured disagreement</Text>
        <Text style={styles.mutedText}>Bull and Bear claims are separate from the neutral Judge. A canonical Debate can pause after its interim Judge so you can make an evidence-grounded challenge before the final assessment.</Text>
      </View>
      <View style={styles.aboutCard}>
        <Text accessibilityRole="header" style={styles.cardTitle}>Safety boundary</Text>
        <Text style={styles.mutedText}>This app explains evidence and uncertainty. It does not provide buy, sell, hold, or personalised financial advice.</Text>
      </View>
      <View style={styles.diagnosticDisclosure}>
        <Pressable
          accessibilityLabel={`${showTechnicalDetails ? "Hide" : "Show"} technical and configuration details`}
          accessibilityRole="button"
          accessibilityState={{ expanded: showTechnicalDetails }}
          onPress={() => setShowTechnicalDetails((current) => !current)}
          style={styles.diagnosticDisclosureButton}
        >
          <Text style={styles.diagnosticDisclosureTitle}>Technical details</Text>
          <Text style={styles.diagnosticDisclosureAction}>{showTechnicalDetails ? "Hide" : "Show"}</Text>
        </Pressable>
        {showTechnicalDetails ? (
          <View style={styles.diagnosticPanel}>
            <Text style={styles.traceLine}>The default demo uses deterministic cached data and needs no API key.</Text>
            <Text style={styles.traceLine}>Optional authentication and model providers are configured outside the app; explanations remain read-only and the V2 Debate interface is off by default.</Text>
          </View>
        ) : null}
      </View>
      {onSignOut ? <Pressable accessibilityLabel="Sign out" accessibilityRole="button" style={styles.secondaryButton} onPress={onSignOut}><Text style={styles.secondaryButtonText}>Sign out</Text></Pressable> : null}
    </ScrollView>
  );
}
