import { createContext } from "react";
import type { Role, User } from "@/lib/types";

export interface AuthContextValue {
  user: User | null;
  role: Role | undefined;
  isLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signInAsDemo: (role: Role) => Promise<void>;
  signOut: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
