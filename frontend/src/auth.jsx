import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useLayoutEffect, useState } from "react";

import { apiFetch, setAuth } from "@/api";
import { clearSession, loadSession, saveSession } from "@/lib";

// --- AuthProvider ------------------------------------------------------------------------------

/** Holds the session (token + user) and gives the token to apiFetch(); a 401 ends it. */
export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState(loadSession);
  const [loggedOutOnPurpose, setLoggedOutOnPurpose] = useState(false);

  function endSession() {
    clearSession();
    setSession(null);
    queryClient.clear(); // never show one user's cached data to the next
  }

  function logout() {
    setLoggedOutOnPurpose(true);
    endSession();
  }

  // A layout effect, not useEffect: React runs all layout effects before any
  // useEffect, so the token is in place before pages start fetching.
  useLayoutEffect(() => {
    setAuth(session?.accessToken ?? null, endSession);
  }, [session]);

  async function login(email, password) {
    const data = await apiFetch("/api/v1/auth/login", {
      method: "POST",
      body: { email, password },
    });
    const next = { accessToken: data.access_token, user: data.user };
    saveSession(next);
    setLoggedOutOnPurpose(false);
    setSession(next);
    return data.user;
  }

  const value = { user: session?.user ?? null, login, logout, loggedOutOnPurpose };

  return <AuthContext value={value}>{children}</AuthContext>;
}

// --- useAuth -----------------------------------------------------------------------------------

/** { user, login(email, password), logout(), loggedOutOnPurpose } from AuthProvider. */
export const AuthContext = createContext(null);

/** Current user plus login/logout. Use inside <AuthProvider>. */
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth() must be used inside <AuthProvider>");
  return value;
}
