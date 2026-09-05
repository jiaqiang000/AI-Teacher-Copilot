"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { RememberSessionOption } from "@/components/auth/remember-session-option";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/core/auth/AuthProvider";
import { resolveAuthNextPath } from "@/core/auth/next-path";
import {
  loadRememberLoginPreference,
  saveRememberLoginPreference,
} from "@/core/auth/remember-login";
import {
  canCreateRegularAccount,
  fetchSetupStatus,
  type SetupStatusResponse,
} from "@/core/auth/setup";
import { parseAuthError } from "@/core/auth/types";
import { useI18n } from "@/core/i18n/hooks";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated } = useAuth();
  const { t } = useI18n();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [isLogin, setIsLogin] = useState(true);
  const [setupStatus, setSetupStatus] = useState<SetupStatusResponse | null>(
    null,
  );
  const [setupStatusPhase, setSetupStatusPhase] = useState<
    "checking" | "ready" | "unavailable"
  >("checking");
  const [setupStatusAttempt, setSetupStatusAttempt] = useState(0);

  // Extract error from query params (e.g., ?error=sso_failed)
  const errorParam = searchParams.get("error");
  const [error, setError] = useState(
    errorParam
      ? (t.login.errors[errorParam as keyof typeof t.login.errors] ??
          t.login.authFailed)
      : "",
  );
  const [loading, setLoading] = useState(false);
  const [demoRole, setDemoRole] = useState<"teacher" | "student" | null>(null);
  // 同步锁防止快速连点同时签发不同身份的会话。
  const loginPending = useRef(false);

  // Get next parameter for validated redirect
  const nextParam = searchParams.get("next");
  const redirectPath = resolveAuthNextPath(nextParam);
  const regularSignupAllowed = canCreateRegularAccount({
    // A failed probe must not expose registration while the system's setup
    // state is unknown. Existing users can still sign in normally.
    checked: setupStatusPhase === "ready",
    status: setupStatus,
  });
  const systemNeedsAdminSetup = setupStatus?.needs_setup === true;
  const showSetupStatusUnavailable =
    setupStatusPhase === "unavailable" ||
    (setupStatusAttempt > 0 && setupStatusPhase === "checking");

  // Redirect if already authenticated (client-side, post-login)
  useEffect(() => {
    if (isAuthenticated) {
      router.push(redirectPath);
    }
  }, [isAuthenticated, redirectPath, router]);

  useEffect(() => {
    const preference = loadRememberLoginPreference();
    setRememberMe(preference.rememberMe);
    if (preference.email) {
      setEmail(preference.email);
    }
  }, []);

  // Fetch setup state independently so retrying a slow Gateway does not also
  // refetch unrelated auth-provider configuration.
  useEffect(() => {
    let cancelled = false;
    setSetupStatusPhase("checking");

    void fetchSetupStatus()
      .then((data) => {
        if (cancelled) return;
        setSetupStatus(data);
        setSetupStatusPhase("ready");
        if (data.needs_setup) {
          setIsLogin(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSetupStatus(null);
          setSetupStatusPhase("unavailable");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [setupStatusAttempt]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loginPending.current) return;
    loginPending.current = true;
    setError("");
    setLoading(true);

    if (!isLogin && !regularSignupAllowed) {
      setError(t.login.adminSetupRequiredDescription);
      setLoading(false);
      loginPending.current = false;
      return;
    }

    try {
      const endpoint = isLogin
        ? "/api/v1/auth/login/local"
        : "/api/v1/auth/register";
      const body = isLogin
        ? new URLSearchParams({
            password,
            remember_me: String(rememberMe),
            username: email,
          })
        : JSON.stringify({ email, password, remember_me: rememberMe });

      const headers: HeadersInit = isLogin
        ? { "Content-Type": "application/x-www-form-urlencoded" }
        : { "Content-Type": "application/json" };

      const res = await fetch(endpoint, {
        method: "POST",
        headers,
        body,
        credentials: "include", // Important: include HttpOnly cookie
      });

      if (!res.ok) {
        const data = await res.json();
        const authError = parseAuthError(data);
        setError(authError.message);
        return;
      }

      saveRememberLoginPreference({ email, rememberMe });

      // Both login and register set a cookie — redirect to workspace
      router.push(redirectPath);
    } catch {
      setError(t.login.networkError);
    } finally {
      setLoading(false);
      loginPending.current = false;
    }
  };

  const handleDemoLogin = async (role: "teacher" | "student") => {
    if (loginPending.current) return;
    loginPending.current = true;
    setDemoRole(role);
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/v1/auth/login/demo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ role, remember_me: rememberMe }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(parseAuthError(data).message);
        setLoading(false);
        setDemoRole(null);
        loginPending.current = false;
        return;
      }
      // 不填充或保存体验凭据；整页导航重新读取 Cookie，并按真实角色分流。
      // 不沿用 next 参数，避免进入另一个角色的页面。
      window.location.assign("/workspace");
    } catch {
      setError(t.login.networkError);
      setLoading(false);
      setDemoRole(null);
      loginPending.current = false;
    }
  };

  return (
    <div className="bg-background relative flex min-h-screen items-center justify-center overflow-x-hidden overflow-y-auto p-6">
      {/* Figma 76:3：邮箱密码在上、静默演示入口在下。 */}
      <div
        aria-hidden
        className="from-background via-background to-primary/10 absolute inset-0 z-0 bg-gradient-to-b"
      />
      <div className="border-border bg-background relative z-10 w-full max-w-xl space-y-6 rounded-3xl border p-6 sm:p-8">
        <div className="text-center">
          <h1 className="text-foreground font-serif text-3xl">智能作业批改</h1>
          <p className="text-muted-foreground mt-2">
            {isLogin ? "教师智能助手——让每一份作业都被看见" : "创建账号"}
          </p>
        </div>

        {showSetupStatusUnavailable && (
          <div
            role="status"
            aria-live="polite"
            className="border-l-2 border-amber-500 ps-3 text-sm"
          >
            <p className="font-medium">{t.login.serviceUnavailableTitle}</p>
            <p className="text-muted-foreground mt-1">
              {t.login.serviceUnavailableDescription}
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-3"
              disabled={setupStatusPhase === "checking"}
              onClick={() => {
                setSetupStatusPhase("checking");
                setSetupStatusAttempt((attempt) => attempt + 1);
              }}
            >
              {setupStatusPhase === "checking"
                ? t.login.pleaseWait
                : t.login.retry}
            </Button>
          </div>
        )}

        {systemNeedsAdminSetup && (
          <div className="border-l-2 border-blue-500 ps-3 text-sm">
            <p className="font-medium">{t.login.adminSetupRequiredTitle}</p>
            <p className="text-muted-foreground mt-1">
              {t.login.adminSetupRequiredDescription}
            </p>
            <Link
              href="/setup"
              className="mt-2 inline-block font-medium text-blue-500 hover:underline"
            >
              {t.login.createAdminAccount}
            </Link>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-2">
          <div className="flex flex-col space-y-1">
            <label htmlFor="email" className="text-sm font-medium">
              {t.login.email}
            </label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t.login.emailPlaceholder}
              required
            />
          </div>
          <div className="flex flex-col space-y-1">
            <label htmlFor="password" className="text-sm font-medium">
              {t.login.password}
            </label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t.login.passwordPlaceholder}
              required
              minLength={isLogin ? 6 : 8}
            />
          </div>

          <RememberSessionOption
            checked={rememberMe}
            onCheckedChange={setRememberMe}
          />

          {error && (
            <p role="alert" className="text-sm text-red-500">
              {error}
            </p>
          )}

          <Button type="submit" className="w-full" disabled={loading}>
            {loading
              ? t.login.pleaseWait
              : isLogin
                ? t.login.signIn
                : t.login.createAccount}
          </Button>
        </form>

        <p className="text-muted-foreground text-center text-xs">
          或选择下方演示身份，一键进入体验
        </p>
        <div className="grid gap-4 sm:grid-cols-2" aria-label="演示登录">
          {(
            [
              {
                role: "teacher",
                title: "教师演示",
                description: "出题、发布、学情画像、作业分析、Copilot 问答",
              },
              {
                role: "student",
                title: "学生演示",
                description: "查看作业、上传作答、实时批改进度与结果",
              },
            ] as const
          ).map(({ role, title, description }) => (
            <button
              key={role}
              type="button"
              aria-label={title}
              aria-busy={demoRole === role}
              disabled={loading || systemNeedsAdminSetup}
              onClick={() => void handleDemoLogin(role)}
              className="border-border hover:border-primary focus-visible:ring-ring flex flex-col gap-2 rounded-[14px] border p-5 text-left transition-colors focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span className="text-lg font-medium">{title}</span>
              <span className="text-muted-foreground text-sm leading-5">
                {description}
              </span>
              <span
                className="text-primary mt-auto text-xs leading-5"
                aria-live="polite"
              >
                {demoRole === role ? "正在登录…" : `使用${title}账号 →`}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
