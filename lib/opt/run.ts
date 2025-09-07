"use client";

import type { MergedPlayer } from "@/lib/domain/types";
import type { OptimizationRequest, OptimizationResult, OptimizerConfig, RunOptions, WorkerMessageOut } from "@/lib/opt/types";

export type RunHandle = { cancel: () => void };

export function runInWorker(
  players: MergedPlayer[],
  config: OptimizerConfig,
  seed: string | number,
  targetLineups: number,
  onEvent?: (msg: WorkerMessageOut) => void,
  options?: RunOptions
): { handle: RunHandle; promise: Promise<OptimizationResult> } {
  const worker = new Worker(new URL("../../workers/optimizer.worker.ts", import.meta.url));
  let done = false;
  const promise = new Promise<OptimizationResult>((resolve, reject) => {
    worker.onmessage = (ev: MessageEvent<WorkerMessageOut>) => {
      const msg = ev.data;
      onEvent?.(msg);
      if (msg.type === "error") {
        if (!done) {
          done = true;
          worker.terminate();
          reject(new Error(msg.message));
        }
      } else if (msg.type === "done") {
        if (!done) {
          done = true;
          worker.terminate();
          resolve(msg.res);
        }
      }
    };
    const req: OptimizationRequest = {
      players,
      config,
      seed: options?.seed ?? seed,
      targetLineups,
      maxCandidates: options?.candidates,
      options,
    };
    worker.postMessage({ type: "run", req });
  });
  return {
    handle: {
      cancel() {
        if (!done) worker.postMessage({ type: "cancel" });
      },
    },
    promise,
  };
}
