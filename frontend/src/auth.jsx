import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useLayoutEffect, useState } from "react";

import { apiFetch, setAuth } from "@/api";
import { clearSession, loadSession, saveSession } from "@/lib";

// What useAuth() gives: user, login, logout, clickedLogout.
export const AuthContext = createContext(null);

/** Holds the saved login (token + user) and gives the token to apiFetch(); a 401 ends it. */
export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const [savedLogin, setSavedLogin] = useState(loadSession());
  const [clickedLogout, setClickedLogout] = useState(false);

  function endSession() {
    clearSession();
    setSavedLogin(null);
    queryClient.clear(); // never show one user's cached data to the next
  }

  function logout() {
    setClickedLogout(true);
    endSession();
  }

  // Give the token to apiFetch before the pages load their data.
  useLayoutEffect(() => {
    const token = savedLogin ? savedLogin.accessToken : null;
    setAuth(token, endSession);
  }, [savedLogin]);

  async function login(email, password) {
    const data = await apiFetch("/api/v1/auth/login", {
      method: "POST",
      body: { email, password },
    });
    const newLogin = { accessToken: data.access_token, user: data.user };
    saveSession(newLogin);
    setClickedLogout(false);
    setSavedLogin(newLogin);
    return data.user;
  }

  const user = savedLogin ? savedLogin.user : null;
  const shared = { user, login, logout, clickedLogout };

  return <AuthContext.Provider value={shared}>{children}</AuthContext.Provider>;
}

/** Current user plus login/logout. Use inside <AuthProvider>. */
export function useAuth() {
  const shared = useContext(AuthContext);
  if (!shared) throw new Error("useAuth() must be used inside <AuthProvider>");
  return shared;
}
