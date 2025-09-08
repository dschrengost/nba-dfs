import { NextRequest } from "next/server";
import { promises as fs } from "fs";
import path from "path";

type RunRow = {
  run_id: string;
  slate_key: string;
  module: string;
  created_at?: string;
  path: string;
  meta?: any;
};

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const module = String(searchParams.get("module") || "optimizer");
    const slate = String(searchParams.get("slate") || "").trim();
    const limit = Number(searchParams.get("limit") || 10);
    const baseRoot = path.join(process.cwd(), "runs");
    let slates: string[] = [];
    try {
      if (slate && slate.toLowerCase() !== "all") {
        slates = [slate];
      } else {
        const dirs = await fs.readdir(baseRoot);
        slates = dirs.filter((d) => !d.startsWith("."));
      }
    } catch {
      return Response.json({ ok: true, runs: [], base: baseRoot });
    }

    const rows: (RunRow & { _ts: number })[] = [];
    for (const s of slates) {
      const base = path.join(baseRoot, s, module);
      let entries: string[] = [];
      try {
        entries = await fs.readdir(base);
      } catch {
        continue;
      }
      for (const name of entries) {
        if (!name || name.startsWith("__tmp__")) continue;
        const runDir = path.join(base, name);
        try {
          const stat = await fs.stat(runDir);
          if (!stat.isDirectory()) continue;
          const metaPath = path.join(runDir, "run_meta.json");
          let meta: any = undefined;
          try {
            const raw = await fs.readFile(metaPath, "utf8");
            meta = JSON.parse(raw);
          } catch {}
          let ts = stat.mtimeMs;
          const created = meta?.created_at;
          if (typeof created === "string") {
            const d = new Date(created);
            if (!isNaN(d.getTime())) ts = d.getTime();
          }
          rows.push({ run_id: name, slate_key: s, module, created_at: meta?.created_at, path: runDir, meta, _ts: ts });
        } catch {}
      }
    }
    rows.sort((a, b) => b._ts - a._ts);
    const out = (limit > 0 ? rows.slice(0, limit) : rows).map(({ _ts, ...r }) => r);
    return Response.json({ ok: true, runs: out, base: baseRoot, slates });
  } catch (e: any) {
    return new Response(String(e?.message || e), { status: 500 });
  }
}
export const dynamic = "force-dynamic";
