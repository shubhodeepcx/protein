"use client";

import React, { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Upload, Loader2, AlertCircle, FileText } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiPost, ApiError } from "@/lib/api";
import type { ProteinSummary } from "@/lib/types";

const ALLOWED_EXTS = ["pdb", "cif", "mmcif"] as const;
const MAX_BYTES = 50 * 1024 * 1024;

type AllowedExt = (typeof ALLOWED_EXTS)[number];

function getExt(name: string): string {
  const i = name.lastIndexOf(".");
  return i === -1 ? "" : name.slice(i + 1).toLowerCase();
}

function validate(file: File): string | null {
  const ext = getExt(file.name);
  if (!ALLOWED_EXTS.includes(ext as AllowedExt)) {
    return `Unsupported extension '.${ext}'. Allowed: .pdb, .cif, .mmcif`;
  }
  if (file.size === 0) return "File is empty.";
  if (file.size > MAX_BYTES) {
    return `File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Max 50 MB.`;
  }
  return null;
}

export function DropZone({ className }: { className?: string }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  const upload = useCallback(
    async (file: File) => {
      const validationErr = validate(file);
      if (validationErr) {
        setError(validationErr);
        return;
      }
      setError(null);
      setFileName(file.name);
      setIsUploading(true);

      const form = new FormData();
      form.append("file", file);

      try {
        const summary = await apiPost<ProteinSummary>(
          "/api/proteins/upload",
          form,
        );
        router.push(`/viewer/${summary.id}`);
      } catch (e) {
        if (e instanceof ApiError) {
          const detail =
            typeof e.body === "object" && e.body !== null
              ? ((e.body.detail as string | undefined) ??
                (e.body.error as string | undefined) ??
                null)
              : null;
          setError(`Upload failed (${e.status}): ${detail ?? e.message}`);
        } else {
          setError(
            `Upload failed: ${e instanceof Error ? e.message : String(e)}`,
          );
        }
        setIsUploading(false);
        setFileName(null);
      }
    },
    [router],
  );

  function handleClick() {
    if (isUploading) return;
    inputRef.current?.click();
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) void upload(file);
    e.target.value = ""; // allow re-picking same file
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    if (!isUploading) setIsDragging(true);
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
    if (isUploading) return;
    const file = e.dataTransfer.files[0];
    if (file) void upload(file);
  }

  return (
    <Card
      data-testid="drop-zone"
      data-dragging={isDragging ? "true" : "false"}
      data-uploading={isUploading ? "true" : "false"}
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleClick();
        }
      }}
      onDragOver={handleDragOver}
      onDragEnter={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`relative flex w-full max-w-2xl cursor-pointer flex-col items-center justify-center border-2 border-dashed p-10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background ${
        isDragging
          ? "border-primary bg-primary/5"
          : "border-border/60 hover:border-border"
      } ${isUploading ? "pointer-events-none opacity-70" : ""} ${className ?? ""}`}
      aria-label="Upload protein structure"
      aria-busy={isUploading}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdb,.cif,.mmcif"
        className="hidden"
        onChange={handleInputChange}
        disabled={isUploading}
        data-testid="drop-zone-input"
      />

      <CardContent className="flex flex-col items-center gap-3 text-center">
        {isUploading ? (
          <>
            <Loader2
              className="size-8 animate-spin text-primary"
              aria-hidden
            />
            <p className="text-sm font-medium">Uploading {fileName}&hellip;</p>
            <p className="text-xs text-muted-foreground">
              Parsing structure on the server. This usually takes a few
              seconds.
            </p>
          </>
        ) : (
          <>
            <Upload className="size-8 text-muted-foreground" aria-hidden />
            <p className="text-sm font-medium">
              Drop a <code className="font-mono">.pdb</code> or{" "}
              <code className="font-mono">.cif</code> file here
            </p>
            <p className="text-xs text-muted-foreground">
              or click to browse (up to 50 MB)
            </p>
            <Button
              size="sm"
              variant="secondary"
              className="mt-2"
              tabIndex={-1}
            >
              <FileText aria-hidden className="size-3.5" />
              Choose file
            </Button>
          </>
        )}

        {error && (
          <div
            role="alert"
            className="mt-3 flex items-start gap-2 rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-left text-xs text-destructive"
          >
            <AlertCircle
              className="mt-0.5 size-3.5 shrink-0"
              aria-hidden
            />
            <span>{error}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default DropZone;
