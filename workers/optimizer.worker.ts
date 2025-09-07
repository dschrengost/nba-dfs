/// <reference lib="webworker" />

import type { OptimizationRequest, WorkerMessageIn, WorkerMessageOut } from "@/lib/opt/types";
import { greedyRandom } from "@/lib/opt/algorithms/greedy";

let cancelled = false;

function post(msg: WorkerMessageOut) {
  // @ts-ignore - in worker scope, self.postMessage exists
  postMessage(msg);
}

async function runOptimization(req: OptimizationRequest) {
  return greedyRandom(req, (tried, valid) => {
    if (cancelled) return;
    post({ type: "progress", tried, valid });
  });
}

// Message handler
self.onmessage = async (e: MessageEvent<WorkerMessageIn>) => {
  const msg = e.data;
  if (msg.type === "cancel") {
    cancelled = true;
    return;
  }
  if (msg.type === "run") {
    cancelled = false;
    try {
      post({ type: "started", at: Date.now() });
      const t0 = performance.now();
      const res = await runOptimization(msg.req);
      if (cancelled) return; // silent cancel
      const elapsedMs = Math.round(performance.now() - t0);
      res.summary.elapsedMs = elapsedMs;
      post({ type: "done", res });
    } catch (err: any) {
      post({ type: "error", message: err?.message ?? String(err) });
    }
  }
};

export {}; // keep this a module
