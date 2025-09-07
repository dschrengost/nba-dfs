"use client";

import { Card } from "./card";

type Props = {
  spotlight?: boolean;
};

export default function UploadDropzone({ spotlight = false }: Props) {
  return (
    <Card
      role="region"
      aria-label="Upload Dropzone"
      tabIndex={0}
      className={`h-[40px] w-[350px] border-dashed px-4 flex items-center text-sm ${
        spotlight ? "shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]" : ""
      }`}
    >
      Drag & drop projections.csv / player_ids.csv
    </Card>
  );
}
