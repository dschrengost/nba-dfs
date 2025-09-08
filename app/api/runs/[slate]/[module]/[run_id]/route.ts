import { NextRequest } from "next/server";
import { promises as fs } from "fs";
import path from "path";

async function readJson(p: string): Promise<any | undefined> {
  try {
    const raw = await fs.readFile(p, "utf8");
    return JSON.parse(raw);
  } catch {
    return undefined;
  }
}

export async function GET(_req: NextRequest, ctx: { params: { slate: string; module: string; run_id: string } }) {
  try {
    const { slate, module, run_id } = ctx.params;
    const base = path.join(process.cwd(), "runs", slate, module, run_id);
    const meta = await readJson(path.join(base, "run_meta.json"));
    if (!meta) return new Response("Not found", { status: 404 });
    const artifactsDir = path.join(base, "artifacts");
    const lineups = await readJson(path.join(artifactsDir, "lineups_json")) ?? await readJson(path.join(artifactsDir, "lineups.json"));
    const diagnostics = await readJson(path.join(artifactsDir, "diagnostics_json")) ?? await readJson(path.join(artifactsDir, "diagnostics.json"));
    const summary = await readJson(path.join(artifactsDir, "summary_json")) ?? meta.summary ?? undefined;
    return Response.json({ ok: true, run: { slate_key: slate, module, run_id, meta, lineups, diagnostics, summary } });
  } catch (e: any) {
    return new Response(String(e?.message || e), { status: 500 });
  }
}
export const dynamic = "force-dynamic";
