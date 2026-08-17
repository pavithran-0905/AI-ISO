"use client";

import { Eye, EyeOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { getLoginErrorMessage } from "@/auth/login-error";
import { isMfaChallenge } from "@/auth/types";
import { useLogin } from "@/auth/use-login";
import { Alert } from "@/components/feedback/alert";
import { Checkbox } from "@/components/forms/checkbox";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";

/**
 * `@hookform/resolvers` (the usual React-Hook-Form/Zod bridge) isn't a
 * repository dependency, and the two rules this form needs (required,
 * valid email format) don't justify adding one (docs/frontend
 * Prompt 004 §33: "do not install unnecessary packages") — `safeParse`
 * inside `onSubmit`, wired to RHF's own `setError`, gets the same
 * result with zero new dependencies.
 */
const loginSchema = z.object({
  email: z.string().trim().min(1, "Email is required").email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
  rememberMe: z.boolean(),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginForm({ returnTo }: { returnTo: string }) {
  const router = useRouter();
  const login = useLogin();
  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({ defaultValues: { email: "", password: "", rememberMe: false } });

  async function onSubmit(values: LoginFormValues) {
    setFormError(null);
    const parsed = loginSchema.safeParse(values);
    if (!parsed.success) {
      // A blank email fails both `.min(1)` and `.email()` — only the
      // first (more accurate: "required", not "invalid format") should
      // reach the user, so later issues for an already-erroring field
      // are skipped rather than overwriting it.
      const seenFields = new Set<string>();
      for (const issue of parsed.error.issues) {
        const field = issue.path[0] as keyof LoginFormValues;
        if (seenFields.has(field)) continue;
        seenFields.add(field);
        setError(field, { message: issue.message });
      }
      return;
    }

    try {
      const result = await login.mutateAsync({
        email: parsed.data.email,
        password: parsed.data.password,
        rememberMe: parsed.data.rememberMe,
      });
      if (isMfaChallenge(result)) {
        // Backend V1 Integration Limitation: `POST /auth/login` can
        // return an MFA challenge, but no MFA-code UI exists yet — see
        // docs/frontend/backend-v1-integration-limitations.md.
        setFormError(
          "This account requires multi-factor authentication, which isn't supported in this interface yet. Contact your administrator.",
        );
        return;
      }
      router.push(returnTo);
    } catch (error) {
      setFormError(getLoginErrorMessage(error));
    }
  }

  const busy = isSubmitting || login.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
      {formError && (
        <Alert tone="danger" title="Sign-in failed">
          {formError}
        </Alert>
      )}

      <FormField label="Email" required error={errors.email?.message}>
        {(fieldProps) => (
          <Input
            {...fieldProps}
            {...register("email")}
            type="email"
            autoComplete="username"
            invalid={Boolean(errors.email)}
            disabled={busy}
          />
        )}
      </FormField>

      <FormField label="Password" required error={errors.password?.message}>
        {(fieldProps) => (
          <div className="relative">
            <Input
              {...fieldProps}
              {...register("password")}
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              invalid={Boolean(errors.password)}
              disabled={busy}
              className="pr-9"
            />
            <IconButton
              icon={showPassword ? EyeOff : Eye}
              aria-label={showPassword ? "Hide password" : "Show password"}
              variant="ghost"
              className="absolute top-1/2 right-0.5 -translate-y-1/2"
              onClick={() => setShowPassword((value) => !value)}
              disabled={busy}
            />
          </div>
        )}
      </FormField>

      <div className="flex items-center gap-2">
        <Checkbox id="remember-me" {...register("rememberMe")} disabled={busy} />
        <Label htmlFor="remember-me">Keep me signed in</Label>
      </div>

      <Button type="submit" variant="primary" loading={busy} disabled={busy} className="w-full">
        Sign In
      </Button>
    </form>
  );
}
