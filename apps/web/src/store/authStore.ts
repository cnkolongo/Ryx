/**
 * Auth store — Zustand
 * Gère le token JWT et le profil utilisateur courant.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { authApi } from "@/lib/api";

interface User {
  user_id: string;
  username: string;
  role: string;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;

  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  setTokens: (access: string, refresh: string) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,

      login: async (username, password) => {
        const { data } = await authApi.login(username, password);
        localStorage.setItem("ryx_access_token", data.access_token);
        localStorage.setItem("ryx_refresh_token", data.refresh_token);

        const { data: user } = await authApi.me();
        set({ user, accessToken: data.access_token, isAuthenticated: true });
      },

      logout: () => {
        localStorage.removeItem("ryx_access_token");
        localStorage.removeItem("ryx_refresh_token");
        set({ user: null, accessToken: null, isAuthenticated: false });
      },

      setTokens: (access, refresh) => {
        localStorage.setItem("ryx_access_token", access);
        localStorage.setItem("ryx_refresh_token", refresh);
        set({ accessToken: access });
      },
    }),
    {
      name: "ryx-auth",
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
);
