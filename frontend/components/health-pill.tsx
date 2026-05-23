"use client";

import { useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

type HealthState =
  | { status: "loading" }
  | { status: "ok"; version?: string }
  | { status: "error"; message: string };

/**
 * Pings the backend `/health` endpoint on mount and renders a small status pill.
 * Green dot when reachable, red dot when not.
 */
export function HealthPill() {
  const [state, setState] = useState<HealthState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    apiGet<HealthResponse>("/health")
      .then((res) => {
        if (cancelled) return;
        setState({ status: "ok", version: res.version });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message =
          err instanceof ApiError
            ? `Backend ${err.status}`
            : err instanceof Error
              ? err.message
              : "Backend unreachable";
        setState({ status: "error", message });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const isOk = state.status === "ok";
  const isLoading = state.status === "loading";

  return (
    <div
      role="status"
      aria-live="polite"
      title={
        state.status === "error"
          ? state.message
          : state.status === "ok" && state.version
            ? `Backend ${state.version}`
            : undefined
      }
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium",
        isLoading && "border-muted-foreground/30 text-muted-foreground",
        isOk && "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
        state.status === "error" &&
          "border-red-500/40 bg-red-500/10 text-red-600 dark:text-red-400",
      )}
    >
      <span
        className={cn(
          "size-2 rounded-full",
          isLoading && "animate-pulse bg-muted-foreground/60",
          isOk && "bg-emerald-500",
          state.status === "error" && "bg-red-500",
        )}
      />
      {isLoading && "Checking backend…"}
      {isOk && "Backend OK"}
      {state.status === "error" && "Backend unreachable"}
    </div>
  );
}
