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
    // Never try to refresh in response to the refresh call itself failing:
    // it would await its own pending refreshPromise and hang forever.
    const isRefreshCall = original?.url?.includes("/auth/refresh");
    if (error.response?.status === 401 && tokenStorage.refresh && !original._retried && !isRefreshCall) {
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
      redirectToLogin();
    }
    return Promise.reject(friendlyError(error));
  }
);

function redirectToLogin() {
  // The session (or the account itself) is gone: send the user to sign in
  // instead of leaving the app half-working with a stale login.
  tokenStorage.clear();
  // Go to "/" (a real file on static hosts) - the router then sends the
  // signed-out user on to the sign-in page. Hard-navigating to "/login" 404s
  // on hosts without an SPA fallback, such as Vercel's services mode.
  if (window.location.pathname !== "/login" && window.location.pathname !== "/register") {
    window.location.assign("/");
  }
}

/**
 * Turns an axios failure into an Error whose message says what went wrong
 * (the backend's own message when it sent one) and what the user can do next,
 * instead of axios's generic "Request failed with status code 401".
 */
function friendlyError(error: AxiosError): Error {
  const body = error.response?.data as APIResponse<unknown> | undefined;
  const backendMessage = body?.error?.message;
  const status = error.response?.status;
  const url = error.config?.url ?? "";
  const method = (error.config?.method ?? "get").toLowerCase();
  const isAuthCall = url.includes("/auth/login") || url.includes("/auth/register");

  if (!error.response) {
    return new Error(
      error.code === "ECONNABORTED"
        ? "The request timed out. The server or database took too long to respond - try again, or ask a simpler question."
        : "Can't reach the server. Check your internet connection and try again in a moment."
    );
  }

  let hint = "";
  if (status === 401) {
    hint = isAuthCall
      ? "Check your email and password. If you haven't registered yet, click \"Create one\"."
      : "Your session has expired or your account no longer exists. Sign in again (or register if needed).";
  } else if (status === 400 && url.includes("/connections") && method === "post") {
    hint =
      "Check the host, port, database name, username and password. The database must accept connections from the internet (not just localhost), and cloud databases usually need SSL enabled.";
  } else if (status === 400) {
    hint = "The request was rejected. Check the values you entered and try again.";
  } else if (status === 403) {
    hint = "Your account doesn't have permission to do this. Ask an admin for access.";
  } else if (status === 404) {
    hint = "That item no longer exists. Refresh the page and try again.";
  } else if (status === 408) {
    hint = "The query took too long. Try a narrower question or add filters.";
  } else if (status === 409) {
    hint = "That already exists. Use a different value, or sign in if it's your account.";
  } else if (status === 422) {
    hint = "Some fields are missing or invalid. Fix them and try again.";
  } else if (status === 429) {
    hint = "Too many requests. Wait a minute and try again.";
  } else if (status === 502) {
    hint = "The server couldn't reach the database or the AI provider. Check the connection details and your API key, then retry.";
  } else if (status && status >= 500) {
    hint = "Something went wrong on the server. Try again; if it keeps happening, check the server logs.";
  }

  const message = backendMessage ?? `Request failed (HTTP ${status}).`;
  return new Error(hint ? `${message} - ${hint}` : message);
}

/** Unwraps the {success, data, error} envelope and throws a readable Error on failure. */
export async function unwrap<T>(promise: Promise<{ data: APIResponse<T> }>): Promise<T> {
  const { data } = await promise;
  if (!data.success || data.data === null) {
    throw new Error(data.error?.message ?? "Request failed");
  }
  return data.data;
}
