import AsyncStorage from "@react-native-async-storage/async-storage";
import type { Session } from "@supabase/supabase-js";
import { useEffect, useState } from "react";
import { clearPendingInterruptionsForAccount } from "../pendingInterruption";
import { supabase } from "../supabase";

/** Prefer newer auth events over the initial session read and clear account state on changes. */
export function useWorkspaceAuth(onAccountChange: () => void) {
  const [authReady, setAuthReady] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  useEffect(() => {
    if (!supabase) {
      setAuthReady(true);
      return;
    }
    let active = true;
    let previousAccount: string | null = null;
    let initialized = false;
    let authEventSeen = false;
    const adoptSession = (nextSession: Session | null) => {
      const nextAccount = nextSession?.user.id || null;
      if (initialized && previousAccount !== nextAccount) {
        if (previousAccount) {
          void clearPendingInterruptionsForAccount(AsyncStorage, previousAccount).catch(() => {
            // Account-scoped records remain inaccessible to the new account.
          });
        }
        onAccountChange();
      }
      initialized = true;
      previousAccount = nextAccount;
      setSession(nextSession);
      setAuthReady(true);
    };
    void supabase.auth
      .getSession()
      .then(({ data }) => {
        if (active && !authEventSeen) adoptSession(data.session);
      })
      .catch(() => {
        if (active && !authEventSeen) adoptSession(null);
      });
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      authEventSeen = true;
      if (active) adoptSession(nextSession);
    });
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, [onAccountChange]);

  return { authReady, session };
}
