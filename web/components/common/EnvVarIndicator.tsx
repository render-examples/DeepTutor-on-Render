"use client";

import { CheckCircle2, XCircle } from "lucide-react";
import { useTranslation } from "react-i18next";

/**
 * Read-only indicator for an environment-only secret. Provider API keys are
 * never entered in the UI or sent to/from the browser; the server reports only
 * whether the backing env var currently holds a value. Renders a green
 * "Set via environment" or a red "Not set" next to the env var name.
 *
 * ``variant`` picks the layout: ``"box"`` (bordered pill, the default used in
 * the profile/pipeline editors) or ``"inline"`` (compact colored span used in
 * a settings-row control).
 */
export default function EnvVarIndicator({
  envVar,
  isSet,
  variant = "box",
  className = "",
}: {
  /** Env var name to display (e.g. "OPENAI_API_KEY"). */
  envVar: string;
  /** Whether the backing env var currently holds a value. */
  isSet: boolean;
  variant?: "box" | "inline";
  className?: string;
}) {
  const { t } = useTranslation();
  const Icon = isSet ? CheckCircle2 : XCircle;
  const label = isSet ? t("Set via environment") : t("Not set");
  const code = (
    <code className="rounded bg-[var(--muted)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--foreground)]">
      {envVar}
    </code>
  );

  if (variant === "inline") {
    return (
      <span
        className={`inline-flex items-center gap-1.5 text-[12px] ${
          isSet
            ? "text-emerald-600 dark:text-emerald-400"
            : "text-red-600 dark:text-red-400"
        } ${className}`}
      >
        <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
        {label}
        {code}
      </span>
    );
  }

  return (
    <div
      className={`flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border px-3 py-2 text-[12px] text-[var(--muted-foreground)] ${
        isSet
          ? "border-emerald-500/30 bg-emerald-500/5"
          : "border-red-500/30 bg-red-500/5"
      } ${className}`}
    >
      <Icon
        aria-hidden
        className={`h-3.5 w-3.5 shrink-0 ${
          isSet ? "text-emerald-500" : "text-red-500"
        }`}
      />
      <span className="text-[var(--foreground)]/80">{label}</span>
      {code}
    </div>
  );
}
