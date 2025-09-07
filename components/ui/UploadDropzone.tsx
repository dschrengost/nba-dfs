"use client";

import { useEffect, useRef, useState } from "react";
import { Card } from "./card";
import { toast } from "./sonner";
import { UPLOAD_MIN_MS } from "@/lib/ui/constants";
import { prefersReducedMotion } from "@/lib/ui/a11y";
import { useIngestStore } from "@/lib/state/ingest-store";

type Props = { spotlight?: boolean };
type UploadState = "idle" | "dragOver" | "loading" | "success" | "error";

export default function UploadDropzone({ spotlight = false }: Props) {
  const [state, setState] = useState<UploadState>("idle");
  const [message, setMessage] = useState<string>(
    "Drag & drop projections.csv / player_ids.csv"
  );
  const inputRef = useRef<HTMLInputElement>(null);
  const reduced = prefersReducedMotion();

  useEffect(() => {
    if (state === "dragOver") setMessage("Release to upload…");
    else if (state === "loading") setMessage("Uploading…");
    else if (state === "success") setMessage("Projections loaded");
    else if (state === "error") setMessage("Only .csv files are supported");
    else setMessage("Drag & drop projections.csv / player_ids.csv");
  }, [state]);

  async function handleFiles(files: FileList | null) {
    const list = Array.from(files ?? []);
    if (list.length === 0) return;
    const bad = list.find((f) => !f.name.toLowerCase().endsWith(".csv"));
    if (bad) {
      setState("error");
      toast.error("Only .csv files are supported");
      setTimeout(() => setState("idle"), 1200);
      return;
    }
    setState("loading");
    const delay = reduced ? 200 : UPLOAD_MIN_MS;
    try {
      const ingest = useIngestStore.getState().ingestCsv;
      for (const f of list) {
        await ingest(f);
      }
      setTimeout(() => {
        setState("success");
        toast.success("CSV ingested");
        setTimeout(() => setState("idle"), 900);
      }, delay);
    } catch (e: any) {
      setState("error");
      toast.error(e?.message ?? "Failed to ingest CSV");
      setTimeout(() => setState("idle"), 1200);
    }
  }

  return (
    <Card
      role="region"
      aria-label="Upload Dropzone"
      aria-live="polite"
      aria-busy={state === "loading"}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          inputRef.current?.click();
        } else if (e.key === "Escape") {
          setState("idle");
        }
      }}
      onDragEnter={(e) => {
        e.preventDefault();
        setState("dragOver");
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (state !== "dragOver") setState("dragOver");
      }}
      onDragLeave={(e) => {
        e.preventDefault();
        setState("idle");
      }}
      onDrop={(e) => {
        e.preventDefault();
        setState("idle");
        handleFiles(e.dataTransfer?.files ?? null);
      }}
      className={`h-[40px] w-[350px] px-4 flex items-center text-sm transition-colors ${
        spotlight ? "shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]" : ""
      } ${
        state === "dragOver"
          ? "border border-primary bg-primary/5"
          : "border border-dashed"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        multiple
        className="hidden"
        onChange={(e) => handleFiles(e.currentTarget.files)}
      />
      {message}
    </Card>
  );
}
