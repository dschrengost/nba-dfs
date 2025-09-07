import Papa from "papaparse";
import { z } from "zod";

export type ParseReport<T> = {
  rows: T[];
  errors: { row: number; message: string }[];
  rowCount: number;
  droppedRows: number;
  unknownColumns: string[];
};

// Streaming CSV parser with header aliasing + row validation
export function parseCsvStream<T extends z.ZodRawShape>(
  file: File,
  schema: z.ZodObject<T>,
  aliases: Record<string, keyof z.infer<z.ZodObject<T>>>
): Promise<ParseReport<z.infer<typeof schema>>> {
  return new Promise((resolve, reject) => {
    const rows: any[] = [];
    const errors: { row: number; message: string }[] = [];
    let rowCount = 0;
    let droppedRows = 0;
    let unknown: Set<string> | null = null;

    Papa.parse(file, {
      header: true,
      dynamicTyping: false,
      skipEmptyLines: true,
      worker: false,
      step: (results, parser) => {
        const raw = results.data as Record<string, unknown>;
        rowCount += 1;

        // Initialize unknown columns on first row
        if (!unknown) {
          unknown = new Set(
            Object.keys(raw)
              .map((h) => h.trim())
              .filter((h) => !(h.toLowerCase() in aliases))
          );
        }

        // Map aliases → canonical keys
        const mapped: Record<string, unknown> = {};
        for (const [key, val] of Object.entries(raw)) {
          const norm = key.trim().toLowerCase();
          const target = aliases[norm as keyof typeof aliases];
          if (!target) continue;
          mapped[target as string] = val;
        }

        const parsed = schema.safeParse(mapped);
        if (parsed.success) {
          rows.push(parsed.data);
        } else {
          droppedRows += 1;
          const msg = parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; ");
          errors.push({ row: rowCount, message: msg });
        }
      },
      complete: () => {
        resolve({
          rows: rows as any,
          errors,
          rowCount,
          droppedRows,
          unknownColumns: Array.from(unknown ?? []),
        });
      },
      error: (err) => reject(err),
    });
  });
}

