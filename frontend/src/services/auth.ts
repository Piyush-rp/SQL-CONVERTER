import { api, unwrap } from "@/services/api";
import type { TokenPair, User } from "@/types/api";

export const authService = {
  register(email: string, password: string, fullName: string) {
    return unwrap<User>(api.post("/auth/register", { email, password, full_name: fullName }));
  },
  login(email: string, password: string) {
    return unwrap<TokenPair>(api.post("/auth/login", { email, password }));
  },
  me() {
    return unwrap<User>(api.get("/auth/me"));
  },
};
