"use client";

import UploadDropzone from "./UploadDropzone";
import ControlsBar from "./ControlsBar";
import type { GridMode } from "./LineupGridPlaceholder";

export default function PageContainer({
  title,
  children,
  gridMode,
  onGridModeChange,
}: {
  title: string;
  children: React.ReactNode;
  gridMode?: GridMode;
  onGridModeChange?: (m: GridMode) => void;
}) {
  return (
    <div className="relative flex flex-col h-full">
      <div className="p-4">
        <div className="mb-4 flex items-center justify-between gap-4">
          <UploadDropzone />
          <div className="flex-1 flex justify-start ml-8">
            <ControlsBar gridMode={gridMode} onGridModeChange={onGridModeChange} />
          </div>
          <h1 className="text-base font-semibold opacity-80">{title}</h1>
        </div>
        <div className="min-h-[calc(100vh-40px-60px-96px-48px)]">
          {children}
        </div>
      </div>
    </div>
  );
}
