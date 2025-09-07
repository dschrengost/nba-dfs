"use client";

import UploadDropzone from "./UploadDropzone";
import ControlsBar from "./ControlsBar";

export default function PageContainer({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="relative flex flex-col h-full">
      <div className="p-4">
        <div className="mb-4 flex items-center justify-between">
          <UploadDropzone />
          <h1 className="text-base font-semibold opacity-80">{title}</h1>
        </div>
        <div className="min-h-[calc(100vh-40px-60px-96px-48px)]">
          {children}
        </div>
      </div>
      <div className="mt-auto">
        <ControlsBar />
      </div>
    </div>
  );
}

