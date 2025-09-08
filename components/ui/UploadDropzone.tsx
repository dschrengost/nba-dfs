"use client";

import { useEffect, useState } from "react";
import { CheckCircle, FileText, Upload, Loader2, AlertCircle } from "lucide-react";
import { Dropzone, DropzoneContent, DropzoneEmptyState } from "./dropzone";
import { Button } from "./button";
import { Card } from "./card";
import { Badge } from "./badge";
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
    <Card className="w-[240px] bg-card/50 backdrop-blur-sm">
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
          "h-[52px] w-full px-3 py-2 flex-col items-start justify-center gap-1 text-sm border-dashed transition-all rounded-md",
          spotlight && "shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]",
          state === "success" && "border-green-500/50 bg-green-500/10",
          state === "error" && "border-red-500/50 bg-red-500/10", 
          state === "loading" && "border-blue-500/50 bg-blue-500/10",
          state === "idle" && "border-border/50 hover:border-border/80 hover:bg-accent/20"
        )}
      >
        {state === "idle" && uploadedFiles.length === 0 && (
          <DropzoneEmptyState className="flex-col items-center justify-center gap-1 w-full h-full">
            <Upload className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs text-muted-foreground text-center leading-tight">
              Drag & drop projections.csv / player_ids.csv
            </span>
          </DropzoneEmptyState>
        )}

        {state === "loading" && (
          <div className="flex flex-col items-center gap-1 w-full h-full justify-center">
            <Badge variant="secondary" className="bg-blue-500/20 text-blue-600 border-blue-500/30">
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              Uploading
            </Badge>
            <span className="text-xs text-blue-500/80">Processing files...</span>
          </div>
        )}

        {state === "success" && uploadedFiles.length > 0 && (
          <div className="flex flex-col items-center justify-center gap-1 w-full h-full">
            <Badge variant="secondary" className="bg-green-500/20 text-green-600 border-green-500/30">
              <CheckCircle className="h-3 w-3 mr-1" />
              Files loaded
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleReplace}
              className="h-5 px-2 text-xs hover:bg-accent/50 hover:text-foreground"
              data-testid="replace-upload-button"
            >
              Replace
            </Button>
          </div>
        )}

        {state === "error" && (
          <div className="flex flex-col items-center gap-1 w-full h-full justify-center">
            <Badge variant="destructive" className="bg-red-500/20 text-red-600 border-red-500/30">
              <AlertCircle className="h-3 w-3 mr-1" />
              CSV only
            </Badge>
            <span className="text-xs text-red-500/80 text-center">Only .csv files supported</span>
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
    </Card>
  );
}
