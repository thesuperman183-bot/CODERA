"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { apiClient, clearStoredToken, getStoredToken, setStoredToken } from "@/lib/api";

interface UserProfile {
  id: string;
  email: string;
  name: string;
  teams: Array<{
    team_id: string;
    team_name: string;
    role: string;
  }>;
}

interface AuthContextType {
  user: UserProfile | null;
  loading: boolean;
  activeTeamId: string | null;
  setActiveTeamId: (teamId: string | null) => void;
  login: (email: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  activeTeamId: null,
  setActiveTeamId: () => {},
  login: async () => {},
  logout: () => {},
  refreshUser: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTeamId, setActiveTeamId] = useState<string | null>(null);

  const fetchCurrentUser = async () => {
    try {
      let token = getStoredToken();
      if (!token) {
        // Auto-provision initial session for seamless first-load experience
        try {
          const res = await apiClient.auth.login("developer@example.com");
          if (res?.token) {
            setStoredToken(res.token);
            token = res.token;
            setUser(res.user);
            if (res.user?.teams?.length > 0) {
              setActiveTeamId(res.user.teams[0].team_id);
            }
            setLoading(false);
            return;
          }
        } catch {
          // Backend may be offline or unreachable
          setUser(null);
          setLoading(false);
          return;
        }
      }
      const data = await apiClient.auth.me();
      setUser(data);
      if (data.teams && data.teams.length > 0 && !activeTeamId) {
        setActiveTeamId(data.teams[0].team_id);
      }
    } catch {
      setUser(null);
      clearStoredToken();
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCurrentUser();
  }, []);

  const login = async (email: string) => {
    setLoading(true);
    try {
      const res = await apiClient.auth.login(email);
      setStoredToken(res.token);
      setUser(res.user);
      if (res.user?.teams?.length > 0) {
        setActiveTeamId(res.user.teams[0].team_id);
      }
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    clearStoredToken();
    setUser(null);
    setActiveTeamId(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        activeTeamId,
        setActiveTeamId,
        login,
        logout,
        refreshUser: fetchCurrentUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

