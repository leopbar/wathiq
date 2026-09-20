import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { AlertCircle, BadgeCheck, FileSearch, ScrollText } from "lucide-react";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api";
import { qk } from "@/lib/query";
import type { DemoUser, Role } from "@/lib/types";
import { useAuth } from "@/auth/useAuth";
import { describeError } from "@/components/ErrorState";
import { BrandMark } from "@/components/BrandMark";
import { ModeBadge } from "@/components/ModeBadge";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LanguageToggle } from "@/components/LanguageToggle";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { DemoUserCards, DemoUserSkeleton } from "./login/DemoUserCards";

const schema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email address"),
  password: z.string().min(6, "Password must be at least 6 characters"),
});

const TRUST_POINTS = [
  { icon: FileSearch, key: "login.trust1" },
  { icon: BadgeCheck, key: "login.trust2" },
  { icon: ScrollText, key: "login.trust3" },
];

export default function Login() {
  const { t } = useTranslation();
  const { user, isLoading, signIn, signInAsDemo } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [pendingRole, setPendingRole] = useState<Role | null>(null);

  const demoUsers = useQuery({
    queryKey: qk.demoUsers,
    queryFn: () => apiFetch<DemoUser[]>("/auth/demo-users"),
    retry: false,
    staleTime: 5 * 60_000,
  });

  if (isLoading) return <FullPageSpinner />;
  if (user) {
    const from = (location.state as { from?: string } | null)?.from;
    return <Navigate to={from && from !== "/login" ? from : "/"} replace />;
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError(null);
    const parsed = schema.safeParse({ email, password });
    if (!parsed.success) {
      const fieldErrors: { email?: string; password?: string } = {};
      for (const issue of parsed.error.issues) {
        const key = issue.path[0];
        if (key === "email" || key === "password") fieldErrors[key] ??= issue.message;
      }
      setErrors(fieldErrors);
      return;
    }
    setErrors({});
    setSubmitting(true);
    try {
      await signIn(parsed.data.email, parsed.data.password);
      navigate("/", { replace: true });
    } catch (error) {
      setFormError(describeError(error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const demoSignIn = async (role: Role) => {
    setPendingRole(role);
    setFormError(null);
    try {
      await signInAsDemo(role);
      navigate("/", { replace: true });
    } catch (error) {
      const message = describeError(error).message;
      setFormError(message);
      toast.error("Demo sign-in failed", { description: message });
    } finally {
      setPendingRole(null);
    }
  };

  // Azure mode returns [] (or 404s the endpoint) — hide the section entirely.
  const showDemo = demoUsers.isPending || (demoUsers.data?.length ?? 0) > 0;

  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      {/* Brand panel */}
      <aside className="brand-gradient relative hidden flex-col justify-between p-10 text-white lg:flex">
        <div className="flex items-center gap-3">
          <BrandMark className="text-white" size={32} />
          <div>
            <p className="text-h1 font-semibold tracking-tight">Wathiq</p>
            <p className="text-small text-white/70">واثق · confident</p>
          </div>
        </div>

        <div className="max-w-md">
          <p className="text-display font-semibold leading-tight tracking-tight">
            {t("brand.promise")}
          </p>
          <ul className="mt-8 space-y-4">
            {TRUST_POINTS.map(({ icon: Icon, key }) => (
              <li key={key} className="flex gap-3">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/10 ring-1 ring-white/20">
                  <Icon className="h-3.5 w-3.5" aria-hidden />
                </span>
                <span className="text-small leading-5 text-white/85">{t(key)}</span>
              </li>
            ))}
          </ul>
        </div>

        <p className="text-caption text-white/55">
          Synthetic data only. No real customers, documents or institutions are represented.
        </p>
      </aside>

      {/* Form panel */}
      <main className="flex flex-col bg-bg">
        <div className="flex items-center justify-between gap-2 px-6 py-4">
          <div className="flex items-center gap-2.5 lg:hidden">
            <BrandMark className="text-primary" size={24} />
            <span className="text-body font-semibold text-ink">Wathiq</span>
          </div>
          <div className="ms-auto flex items-center gap-1.5">
            <ModeBadge />
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </div>

        <div className="flex flex-1 items-center justify-center px-6 pb-10">
          <div className="w-full max-w-md">
            <h1 className="text-h1 font-semibold tracking-tight text-ink">{t("login.title")}</h1>
            <p className="mt-1 text-body text-ink-2">{t("login.subtitle")}</p>

            <form onSubmit={(e) => void submit(e)} noValidate className="mt-6 space-y-4">
              <Field label={t("login.email")} htmlFor="email" error={errors.email} required>
                <Input
                  id="email"
                  type="email"
                  dir="ltr"
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  aria-invalid={Boolean(errors.email)}
                  aria-describedby={errors.email ? "email-error" : undefined}
                  placeholder="name@wathiq.demo"
                />
              </Field>

              <Field label={t("login.password")} htmlFor="password" error={errors.password} required>
                <Input
                  id="password"
                  type="password"
                  dir="ltr"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  aria-invalid={Boolean(errors.password)}
                  aria-describedby={errors.password ? "password-error" : undefined}
                  placeholder="••••••••"
                />
              </Field>

              {formError ? (
                <p
                  role="alert"
                  className="flex items-start gap-2 rounded-[var(--radius)] border border-danger/30 bg-danger-soft px-3 py-2 text-small text-danger"
                >
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                  {formError}
                </p>
              ) : null}

              <Button type="submit" variant="primary" size="lg" className="w-full" loading={submitting}>
                {t("login.submit")}
              </Button>
            </form>

            {showDemo ? (
              <section className="mt-8" aria-labelledby="demo-heading">
                <div className="mb-3 flex items-center gap-3">
                  <span className="h-px flex-1 bg-border" aria-hidden />
                  <h2 id="demo-heading" className="label-caption text-ink-2">
                    {t("login.demoTitle")}
                  </h2>
                  <span className="h-px flex-1 bg-border" aria-hidden />
                </div>
                <p className="mb-3 text-small text-ink-2">{t("login.demoSubtitle")}</p>
                {demoUsers.isPending ? (
                  <DemoUserSkeleton />
                ) : (
                  <DemoUserCards
                    users={demoUsers.data ?? []}
                    onSelect={(role) => void demoSignIn(role)}
                    pendingRole={pendingRole}
                    disabled={pendingRole !== null || submitting}
                  />
                )}
              </section>
            ) : null}
          </div>
        </div>
      </main>
    </div>
  );
}
