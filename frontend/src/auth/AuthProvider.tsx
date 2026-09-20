import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch, clearToken, getToken, setToken } from "@/lib/api";
import type { LoginResponse, Role, User } from "@/lib/types";
import { AuthContext, type AuthContextValue } from "./context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(getToken()));

  useEffect(() => {
    let cancelled = false;
    if (!getToken()) {
      setIsLoading(false);
      return;
    }
    apiFetch<User>("/auth/me")
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) return;
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const adopt = useCallback(
    (res: LoginResponse) => {
      setToken(res.access_token);
      setUser(res.user);
      queryClient.clear();
    },
    [queryClient],
  );

  const signIn = useCallback(
    async (email: string, password: string) => {
      const res = await apiFetch<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      adopt(res);
    },
    [adopt],
  );

  const signInAsDemo = useCallback(
    async (role: Role) => {
      const res = await apiFetch<LoginResponse>("/auth/demo-login", {
        method: "POST",
        body: JSON.stringify({ role }),
      });
      adopt(res);
    },
    [adopt],
  );

  const signOut = useCallback(() => {
    clearToken();
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({ user, role: user?.role, isLoading, signIn, signInAsDemo, signOut }),
    [user, isLoading, signIn, signInAsDemo, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
