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
  return text || "请求失败";
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
          throw new Error("缺少访问令牌");
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
      setRegisterError("两次输入的密码不一致。");
      return;
    }
    setRegisterSubmitting(true);
    setRegisterError(null);
    void registerUser(registerAccount.trim(), registerPassword)
      .then((payload: any) => {
        const token = String(payload?.access_token || "");
        if (!token) {
          throw new Error("缺少访问令牌");
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
          账户
        </h1>
        <div className="helper" style={{ marginBottom: 16 }}>
          管理员账号固定为 `admin`，密码为 `admin`。普通用户仍可自行注册。
        </div>

        <div className="chip-group" style={{ marginBottom: 16 }}>
          <button
            type="button"
            className="chip-button"
            data-active={mode === "login"}
            onClick={() => switchMode("login")}
          >
            登录
          </button>
          <button
            type="button"
            className="chip-button"
            data-active={mode === "register"}
            onClick={() => switchMode("register")}
          >
            注册
          </button>
        </div>

        {mode === "login" ? (
          <form onSubmit={handleLogin} className="grid" style={{ gap: 12 }}>
            <input
              className="input"
              type="text"
              placeholder="账号"
              value={loginAccount}
              onChange={(event) => setLoginAccount(event.target.value)}
              autoComplete="username"
              required
            />
            <input
              className="input"
              type="password"
              placeholder="密码"
              value={loginPassword}
              onChange={(event) => setLoginPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
            {loginError ? <div className="helper" style={{ color: "#b91c1c" }}>{loginError}</div> : null}
            <button type="submit" className="primary-button" disabled={loginSubmitting}>
              {loginSubmitting ? "登录中..." : "登录"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleRegister} className="grid" style={{ gap: 12 }}>
            <input
              className="input"
              type="text"
              placeholder="账号（3-64 位）"
              value={registerAccount}
              onChange={(event) => setRegisterAccount(event.target.value)}
              autoComplete="username"
              required
            />
            <input
              className="input"
              type="password"
              placeholder="密码（至少 8 位）"
              value={registerPassword}
              onChange={(event) => setRegisterPassword(event.target.value)}
              autoComplete="new-password"
              required
            />
            <input
              className="input"
              type="password"
              placeholder="确认密码"
              value={registerConfirmPassword}
              onChange={(event) => setRegisterConfirmPassword(event.target.value)}
              autoComplete="new-password"
              required
            />
            {registerError ? <div className="helper" style={{ color: "#b91c1c" }}>{registerError}</div> : null}
            <button type="submit" className="primary-button" disabled={registerSubmitting}>
              {registerSubmitting ? "注册中..." : "注册并登录"}
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
