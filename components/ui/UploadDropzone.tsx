"use client";

type Props = {
  spotlight?: boolean;
};

export default function UploadDropzone({ spotlight = false }: Props) {
  return (
    <div
      role="region"
      aria-label="Upload Dropzone"
      tabIndex={0}
      className={`h-[40px] w-[350px] rounded-md border border-dashed border-border bg-card/50 px-4 flex items-center text-sm ${
        spotlight ? "shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]" : ""
      } focus:outline-none focus-visible:ring-2 focus-visible:ring-ring`}
    >
      Drag & drop projections.csv / player_ids.csv
    </div>
  );
}

