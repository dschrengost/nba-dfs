import { NextRequest } from "next/server";
import { spawn } from "child_process";

export async function POST(req: NextRequest) {
  try {
    const payload = await req.json();

    // --- normalize ownership penalty knobs to house schema ---
    const consIn = (payload?.constraints ?? {}) as any;
    const penIn = (consIn?.ownership_penalty ?? {}) as any;
    if (penIn) {
      // accept legacy keys and map to weight_lambda
      if (penIn.weight_lambda == null) {
        if (typeof penIn.lambda_ === "number") penIn.weight_lambda = penIn.lambda_;
        else if (typeof penIn.lambda === "number") penIn.weight_lambda = penIn.lambda;
      }
      // default mode if missing
      if (penIn.mode == null) penIn.mode = "by_points";
      // Allow UI to pass a pseudo-mode "g_curve"; map to by_points + curve_type
      if (penIn.mode === "g_curve") {
        penIn.mode = "by_points";
        if (penIn.curve_type == null) penIn.curve_type = "sigmoid";
      }
      payload.constraints = { ...consIn, ownership_penalty: penIn };
    }

    // Spawn Python CLI via uv
    const proc = spawn("uv", ["run", "python", "scripts/pyopt/optimize_cli.py"], {
      stdio: ["pipe", "pipe", "pipe"],
    });

    const stdoutChunks: Buffer[] = [];
    const stderrChunks: Buffer[] = [];

    proc.stdout.on("data", (d) => stdoutChunks.push(Buffer.from(d)));
    proc.stderr.on("data", (d) => stderrChunks.push(Buffer.from(d)));

    const done = new Promise<{ code: number | null; signal: NodeJS.Signals | null }>((resolve) => {
      proc.on("close", (code, signal) => resolve({ code, signal }));
    });

    proc.stdin.write(Buffer.from(JSON.stringify(payload)));
    proc.stdin.end();

    const { code } = await done;

    const stdout = Buffer.concat(stdoutChunks).toString("utf8").trim();
    const stderr = Buffer.concat(stderrChunks).toString("utf8").trim();

    if (stderr) {
      // Log to server console for debugging; not returned to client unless error
      console.warn("[optimizer stderr]", stderr);
    }

    if (code !== 0) {
      return new Response(`Optimizer process failed (code=${code}): ${stderr}`, { status: 500 });
    }
    try {
      const data = JSON.parse(stdout || "{}");
      return new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
    } catch (e: any) {
      return new Response(`Invalid optimizer output: ${(e as Error).message}\n---\n${stdout}`, { status: 500 });
    }
  } catch (e: any) {
    return new Response(`Bad request: ${(e as Error).message}`, { status: 400 });
  }
}
