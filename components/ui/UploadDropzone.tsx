"use client";

import { useEffect, useState } from "react";
import { CheckCircle, FileText, Upload, Loader2, AlertCircle } from "lucide-react";
import { Dropzone, DropzoneContent, DropzoneEmptyState } from "./dropzone";
import { Button } from "./button";
import { toast } from "./sonner";
import { UPLOAD_MIN_MS } from "@/lib/ui/constants";
import { prefersReducedMotion } from "@/lib/ui/a11y";
import { useIngestStore } from "@/lib/state/ingest-store";
import { cn } from "@/lib/utils";

type Props = { spotlight?: boolean };
type UploadState = "idle" | "loading" | "success" | "error";

export default function UploadDropzone({ spotlight = false }: Props) {
  const [state, setState] = useState<UploadState>("idle");
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const reduced = prefersReducedMotion();

  async function handleFiles(files: File[]) {
    if (files.length === 0) return;
    
    const bad = files.find((f) => !f.name.toLowerCase().endsWith(".csv"));
    if (bad) {
      setState("error");
      toast.error("Only .csv files are supported");
      setTimeout(() => setState("idle"), 2000);
      return;
    }

    setState("loading");
    const delay = reduced ? 200 : UPLOAD_MIN_MS;
    
    try {
      const ingest = useIngestStore.getState().ingestCsv;
      for (const f of files) {
        await ingest(f);
      }
      
      setTimeout(() => {
        setState("success");
        setUploadedFiles(files);
        toast.success("CSV files ingested successfully");
      }, delay);
    } catch (e: any) {
      setState("error");
      toast.error(e?.message ?? "Failed to ingest CSV");
      setTimeout(() => setState("idle"), 2000);
    }
  }

  const handleReplace = () => {
    setState("idle");
    setUploadedFiles([]);
  };

  return (
    <div className="w-[350px]">
      <Dropzone
        accept={{ "text/csv": [".csv"] }}
        maxFiles={10}
        onDrop={handleFiles}
        onError={(error) => {
          setState("error");
          toast.error(error.message);
          setTimeout(() => setState("idle"), 2000);
        }}
        disabled={state === "loading"}
        src={uploadedFiles.length > 0 ? uploadedFiles : undefined}
        className={cn(
          "h-[40px] w-full px-3 py-2 flex-row items-center justify-between gap-2 text-sm border-dashed transition-all",
          spotlight && "shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]",
          state === "success" && "border-green-500/50 bg-green-500/5",
          state === "error" && "border-red-500/50 bg-red-500/5",
          state === "loading" && "border-blue-500/50 bg-blue-500/5"
        )}
      >
        {state === "idle" && uploadedFiles.length === 0 && (
          <DropzoneEmptyState className="flex-row items-center justify-start gap-2 w-full">
            <Upload className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">
              Drag & drop projections.csv / player_ids.csv
            </span>
          </DropzoneEmptyState>
        )}

        {state === "loading" && (
          <div className="flex items-center gap-2 w-full">
            <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
            <span className="text-sm text-blue-600">Uploading...</span>
          </div>
        )}

        {state === "success" && uploadedFiles.length > 0 && (
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="text-sm font-medium text-green-600">Files loaded ✓</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleReplace}
              className="h-6 px-2 text-xs hover:bg-transparent hover:text-primary"
              data-testid="replace-upload-button"
            >
              Replace
            </Button>
          </div>
        )}

        {state === "error" && (
          <div className="flex items-center gap-2 w-full">
            <AlertCircle className="h-4 w-4 text-red-500" />
            <span className="text-sm text-red-600">Only .csv files are supported</span>
          </div>
        )}

        {uploadedFiles.length > 0 && state !== "success" && state !== "error" && (
          <DropzoneContent className="flex-row items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium truncate max-w-[200px]">
                {uploadedFiles.map(f => f.name).join(", ")}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleReplace}
              className="h-6 px-2 text-xs hover:bg-transparent hover:text-primary"
            >
              Replace
            </Button>
          </DropzoneContent>
        )}
      </Dropzone>
    </div>
  );
}
