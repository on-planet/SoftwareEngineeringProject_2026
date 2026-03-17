import { useRouter } from "next/router";
import React, { FormEvent, useEffect, useState } from "react";

import { loginUser, registerUser } from "../services/api";
import { setAuthToken } from "../utils/auth";

type AuthMode = "login" | "register";

function parseApiError(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error);
  try {
    const payload = JSON.parse(text);
    if (payload && typeof payload.detail === "string") {
      return payload.detail;
    }
    if (payload && Array.isArray(payload.detail) && payload.detail.length > 0) {
      const first = payload.detail[0];
      if (first && typeof first.msg === "string") {
        return first.msg;
      }
    }
  } catch {
    // Ignore parse errors.
  }
  return text || "Request failed";
}

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>("login");

  const [loginAccount, setLoginAccount] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginSubmitting, setLoginSubmitting] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  const [registerAccount, setRegisterAccount] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState("");
  const [registerSubmitting, setRegisterSubmitting] = useState(false);
  const [registerError, setRegisterError] = useState<string | null>(null);

  useEffect(() => {
    const queryMode = router.query.mode;
    if (queryMode === "register") {
      setMode("register");
      return;
    }
    if (queryMode === "login") {
      setMode("login");
    }
  }, [router.query.mode]);

  const switchMode = (nextMode: AuthMode) => {
    setMode(nextMode);
    void router.replace(
      {
        pathname: "/auth",
        query: nextMode === "login" ? { mode: "login" } : { mode: "register" },
      },
      undefined,
      { shallow: true },
    );
  };

  const handleLogin = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (loginSubmitting) {
      return;
    }
    setLoginSubmitting(true);
    setLoginError(null);
    void loginUser(loginAccount.trim(), loginPassword)
      .then((payload: any) => {
        const token = String(payload?.access_token || "");
        if (!token) {
          throw new Error("Missing access token");
        }
        setAuthToken(token);
        return router.push("/");
      })
      .catch((err: unknown) => {
        setLoginError(parseApiError(err));
      })
      .finally(() => {
        setLoginSubmitting(false);
      });
  };

  const handleRegister = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (registerSubmitting) {
      return;
    }
    if (registerPassword !== registerConfirmPassword) {
      setRegisterError("Passwords do not match.");
      return;
    }
    setRegisterSubmitting(true);
    setRegisterError(null);
    void registerUser(registerAccount.trim(), registerPassword)
      .then((payload: any) => {
        const token = String(payload?.access_token || "");
        if (!token) {
          throw new Error("Missing access token");
        }
        setAuthToken(token);
        return router.push("/");
      })
      .catch((err: unknown) => {
        setRegisterError(parseApiError(err));
      })
      .finally(() => {
        setRegisterSubmitting(false);
      });
  };

  return (
    <div className="page">
      <section className="card" style={{ maxWidth: 620, margin: "0 auto" }}>
        <h1 className="page-title" style={{ marginBottom: 12 }}>
          Account
        </h1>
        <div className="chip-group" style={{ marginBottom: 16 }}>
          <button
            type="button"
            className="chip-button"
            data-active={mode === "login"}
            onClick={() => switchMode("login")}
          >
            Login
          </button>
          <button
            type="button"
            className="chip-button"
            data-active={mode === "register"}
            onClick={() => switchMode("register")}
          >
            Register
          </button>
        </div>

        {mode === "login" ? (
          <form onSubmit={handleLogin} className="grid" style={{ gap: 12 }}>
            <input
              className="input"
              type="text"
              placeholder="Account"
              value={loginAccount}
              onChange={(event) => setLoginAccount(event.target.value)}
              autoComplete="username"
              required
            />
            <input
              className="input"
              type="password"
              placeholder="Password (at least 8 chars)"
              value={loginPassword}
              onChange={(event) => setLoginPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
            {loginError ? <div className="helper" style={{ color: "#b91c1c" }}>{loginError}</div> : null}
            <button type="submit" className="primary-button" disabled={loginSubmitting}>
              {loginSubmitting ? "Signing in..." : "Sign in"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleRegister} className="grid" style={{ gap: 12 }}>
            <input
              className="input"
              type="text"
              placeholder="Account (4-64 chars, letters/numbers/_/./-)"
              value={registerAccount}
              onChange={(event) => setRegisterAccount(event.target.value)}
              autoComplete="username"
              required
            />
            <input
              className="input"
              type="password"
              placeholder="Password (at least 8 chars)"
              value={registerPassword}
              onChange={(event) => setRegisterPassword(event.target.value)}
              autoComplete="new-password"
              required
            />
            <input
              className="input"
              type="password"
              placeholder="Confirm password"
              value={registerConfirmPassword}
              onChange={(event) => setRegisterConfirmPassword(event.target.value)}
              autoComplete="new-password"
              required
            />
            {registerError ? <div className="helper" style={{ color: "#b91c1c" }}>{registerError}</div> : null}
            <button type="submit" className="primary-button" disabled={registerSubmitting}>
              {registerSubmitting ? "Creating account..." : "Register and sign in"}
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
