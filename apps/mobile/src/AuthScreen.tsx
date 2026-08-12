import React, { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { supabase } from "./supabase";

export function AuthScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const authenticate = async (mode: "sign-in" | "sign-up") => {
    if (!supabase) return;
    setLoading(true);
    setError("");
    setMessage("");
    const result = mode === "sign-in"
      ? await supabase.auth.signInWithPassword({ email: email.trim(), password })
      : await supabase.auth.signUp({ email: email.trim(), password });
    if (result.error) {
      setError(result.error.message);
    } else if (mode === "sign-up" && !result.data.session) {
      setMessage("Account created. Check your email to confirm it, then sign in.");
    }
    setLoading(false);
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.card}>
        <Text style={styles.eyebrow}>AI BULL VS BEAR</Text>
        <Text style={styles.title}>Sign in to your research workspace.</Text>
        <Text style={styles.body}>
          Your watchlist and analysis history are isolated by your Supabase account.
        </Text>
        <TextInput
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          onChangeText={setEmail}
          placeholder="Email"
          style={styles.input}
          value={email}
        />
        <TextInput
          autoCapitalize="none"
          autoComplete="password"
          onChangeText={setPassword}
          placeholder="Password"
          secureTextEntry
          style={styles.input}
          value={password}
        />
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {message ? <Text style={styles.message}>{message}</Text> : null}
        {loading ? <ActivityIndicator color="#1d5c56" style={styles.loader} /> : null}
        <Pressable
          disabled={loading || !email.trim() || password.length < 6}
          onPress={() => void authenticate("sign-in")}
          style={styles.primaryButton}
        >
          <Text style={styles.primaryText}>Sign in</Text>
        </Pressable>
        <Pressable
          disabled={loading || !email.trim() || password.length < 6}
          onPress={() => void authenticate("sign-up")}
          style={styles.secondaryButton}
        >
          <Text style={styles.secondaryText}>Create account</Text>
        </Pressable>
        <Text style={styles.note}>Use at least six password characters. Never paste a password into source code.</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#f5f1e8", justifyContent: "center", padding: 22 },
  card: { backgroundColor: "#fffdf8", borderColor: "#d8d5ca", borderWidth: 1, borderRadius: 20, padding: 22 },
  eyebrow: { color: "#d95c3b", fontSize: 11, fontWeight: "800", letterSpacing: 1.4, marginBottom: 8 },
  title: { color: "#1e2826", fontSize: 30, lineHeight: 36, fontWeight: "800", marginBottom: 10 },
  body: { color: "#71807a", fontSize: 15, lineHeight: 22, marginBottom: 20 },
  input: { borderColor: "#d8d5ca", borderWidth: 1, borderRadius: 12, padding: 13, color: "#1e2826", marginBottom: 12 },
  error: { color: "#8d332b", fontSize: 12, lineHeight: 18, marginBottom: 8 },
  message: { color: "#1d5c56", fontSize: 12, lineHeight: 18, marginBottom: 8 },
  loader: { marginVertical: 8 },
  primaryButton: { backgroundColor: "#d95c3b", borderRadius: 12, padding: 15, alignItems: "center", marginTop: 4 },
  primaryText: { color: "#fff", fontWeight: "800" },
  secondaryButton: { borderColor: "#1d5c56", borderWidth: 1, borderRadius: 12, padding: 14, alignItems: "center", marginTop: 10 },
  secondaryText: { color: "#1d5c56", fontWeight: "800" },
  note: { color: "#71807a", fontSize: 11, lineHeight: 17, marginTop: 14 },
});
