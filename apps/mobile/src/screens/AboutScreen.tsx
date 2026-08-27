import React from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import { appStyles as styles } from "../theme";


export function AboutScreen({ onSignOut }: { onSignOut?: () => void }) {
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text style={styles.eyebrow}>ABOUT THIS DEMO</Text>
      <Text style={styles.detailTitle}>AI Bull vs Bear</Text>
      <Text style={styles.heroBody}>An educational Agentic RAG demo that places technical signals, news, filing evidence, and two competing explanations side by side.</Text>
      <View style={styles.aboutCard}><Text style={styles.cardTitle}>Safety by design</Text><Text style={styles.mutedText}>The app is designed to explain evidence and uncertainty. It does not provide buy, sell, hold, or personalised financial advice.</Text></View>
      <View style={styles.aboutCard}><Text style={styles.cardTitle}>Demo mode</Text><Text style={styles.mutedText}>The default provider uses deterministic cached data so the app can run without API keys. Supabase and model providers can be connected later through environment variables.</Text></View>
      {onSignOut ? <Pressable style={styles.secondaryButton} onPress={onSignOut}><Text style={styles.secondaryButtonText}>Sign out</Text></Pressable> : null}
    </ScrollView>
  );
}

