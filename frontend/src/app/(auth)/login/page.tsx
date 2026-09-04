"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

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
    setError("");
    setLoading(true);

    if (!isLogin && !regularSignupAllowed) {
      setError(t.login.adminSetupRequiredDescription);
      setLoading(false);
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
    }
  };

  return (
    <div className="bg-background relative flex min-h-screen items-center justify-center overflow-x-hidden overflow-y-auto">
      {/* 003:品牌化背景(无 Figma 稿)—— 径向渐变代替 DeerFlow 鹿纹网格 */}
      <div
        aria-hidden
        className="absolute inset-0 z-0 bg-gradient-to-b from-background via-background to-primary/10"
      />
      <div className="border-border/20 bg-background/5 w-full max-w-md space-y-6 rounded-3xl border p-8 backdrop-blur-sm">
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

          {error && <p className="text-sm text-red-500">{error}</p>}

          <Button type="submit" className="w-full" disabled={loading}>
            {loading
              ? t.login.pleaseWait
              : isLogin
                ? t.login.signIn
                : t.login.createAccount}
          </Button>
        </form>

        {/* 003:品牌化隐藏 SSO 登录入口与注册引导,仅保留本地账号登录 */}
        {false && <div className="hidden" />}

      </div>
    </div>
  );
}
