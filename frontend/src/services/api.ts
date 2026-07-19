import axios, { AxiosError } from "axios";
import type { APIResponse, TokenPair } from "@/types/api";

// Tokens live in localStorage so a session survives a page refresh. For
// deployments that want stronger XSS resistance, swap this for httpOnly
// cookies set by the backend + a CSRF token instead - that requires
// corresponding changes in app/core/security.py and the auth router.
const ACCESS_TOKEN_KEY = "sqlcopilot_access_token";
const REFRESH_TOKEN_KEY = "sqlcopilot_refresh_token";

export const tokenStorage = {
  get access() {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },
  set(tokens: TokenPair) {
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
  },
  clear() {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};

export const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  if (tokenStorage.access) {
    config.headers.Authorization = `Bearer ${tokenStorage.access}`;
  }
  return config;
});

// On a 401, try exactly one silent refresh-and-retry before giving up -
// avoids booting the user out on a merely-expired access token.
let refreshPromise: Promise<string | null> | null = null;

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as any;
    if (error.response?.status === 401 && tokenStorage.refresh && !original._retried) {
      original._retried = true;
      refreshPromise =
        refreshPromise ??
        api
          .post<APIResponse<TokenPair>>("/auth/refresh", null, {
            params: { refresh_token: tokenStorage.refresh },
          })
          .then((res) => {
            const data = res.data.data;
            if (data) {
              tokenStorage.set(data);
              return data.access_token;
            }
            return null;
          })
          .catch(() => {
            tokenStorage.clear();
            return null;
          })
          .finally(() => {
            refreshPromise = null;
          });

      const newToken = await refreshPromise;
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      }
    }
    return Promise.reject(error);
  }
);

/** Unwraps the {success, data, error} envelope and throws a readable Error on failure. */
export async function unwrap<T>(promise: Promise<{ data: APIResponse<T> }>): Promise<T> {
  const { data } = await promise;
  if (!data.success || data.data === null) {
    throw new Error(data.error?.message ?? "Request failed");
  }
  return data.data;
}
