"use client";

import { useEffect, useMemo, useState } from "react";
import { listRuns, getRun, currentSlateKeyNY } from "@/lib/runs/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRunStore } from "@/lib/state/run-store";

export default function LoadRunModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [slateKey, setSlateKey] = useState<string>("all");
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const { setOptions } = useRunStore();

  const formatToEST = (isoString: string | null | undefined): string => {
    if (!isoString) return "";
    try {
      const date = new Date(isoString);
      return date.toLocaleString("en-US", {
        timeZone: "America/New_York",
        month: "2-digit",
        day: "2-digit", 
        hour: "2-digit",
        minute: "2-digit",
        hour12: true
      });
    } catch {
      return isoString;
    }
  };

  useEffect(() => {
    if (!open) return;
    try {
      const saved = localStorage.getItem("dfs_slate_key");
      if (saved) setSlateKey(saved);
    } catch {}
    // Auto-list across all slates when opened
    (async () => { try { await doList(); } catch {} })();
  }, [open]);

  const canList = useMemo(() => true, []);

  const doList = async () => {
    if (!canList) return;
    setLoading(true);
    try {
      const rs = await listRuns("optimizer", slateKey || "all", 10);
      setRows(rs);
    } catch (e) {
      console.error(e);
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  const onLoad = async (run_id: string, slate?: string) => {
    try {
      const data = await getRun(slate || slateKey, "optimizer", run_id);
      // Hydrate store summary + options (best-effort)
      const summary = data?.summary || data?.meta?.summary || null;
      const diagnostics = data?.diagnostics || data?.meta?.diagnostics || null;
      const optsUsed = summary?.optionsUsed || diagnostics?.constraints_raw || diagnostics?.constraints || null;
      // Optimistically set ownership knobs if present
      if (optsUsed?.ownership_penalty) {
        const pen = optsUsed.ownership_penalty;
        setOptions({ ownershipPenalty: { enabled: !!pen.enabled, lambda: Number(pen.weight_lambda ?? pen.lambda ?? 0) } as any });
      }
      // Adapt saved lineups JSON into UI shape (mirror runSolve mapping)
      const { lineups } = data || {};
      if (Array.isArray(lineups) && lineups.length > 0) {
        const lineupsUi = lineups.map((lu: any) => {
          const lineup = {
            id: String(lu.lineup_id ?? lu.id ?? Math.random().toString(36).slice(2)),
            slots: (Array.isArray(lu.players) ? lu.players : []).map((pl: any) => ({
              slot: (pl.pos ?? pl.position ?? "UTIL") as any,
              player_id_dk: pl.dk_id ?? pl.player_id,
              name: pl.name,
              team: pl.team,
              salary: pl.salary,
              own_proj: pl.own_proj,
              pos: pl.pos ?? pl.position,
            })),
            salary: Number(lu.total_salary ?? lu.salary_used ?? 0),
            score: Number(lu.total_proj ?? lu.score ?? 0),
            lineup_id: String(lu.lineup_id ?? lu.id ?? Math.random().toString(36).slice(2)),
            salary_used: Number(lu.total_salary ?? lu.salary_used ?? 0),
            salary_left: lu.salary_left !== undefined ? Number(lu.salary_left) : undefined,
            dup_risk: lu.dup_risk !== undefined ? Number(lu.dup_risk) : undefined,
            own_sum: lu.own_sum !== undefined ? Number(lu.own_sum) : undefined,
            own_avg: lu.own_avg !== undefined ? Number(lu.own_avg) : undefined,
            lev_sum: lu.lev_sum !== undefined ? Number(lu.lev_sum) : undefined,
            lev_avg: lu.lev_avg !== undefined ? Number(lu.lev_avg) : undefined,
            num_uniques_in_pool: lu.num_uniques_in_pool !== undefined ? Number(lu.num_uniques_in_pool) : undefined,
            teams_used: lu.teams_used ?? undefined,
            proj_pts_sum: lu.proj_pts_sum !== undefined ? Number(lu.proj_pts_sum) : undefined,
            stack_flags: lu.stack_flags ?? undefined,
          } as any;
          if (Array.isArray(lu.players)) {
            lu.players.forEach((pl: any) => {
              const position = pl.pos ?? pl.position ?? "UTIL";
              (lineup as any)[position] = pl.dk_id ?? pl.player_id;
            });
          }
          return lineup;
        });
        // emulate a success set
        const useRun = useRunStore.getState();
        (useRun as any).reset?.();
        useRunStore.setState({ status: "done", lineups: lineupsUi, summary: { ...(summary || {}), diagnostics, runId: data?.run_id, slateKey: data?.slate_key }, tried: lineupsUi.length, valid: lineupsUi.length });
      } else {
        // Handle case where lineups are missing or empty
        console.warn(`No lineups found for run ${run_id}. Loading run metadata only.`);
        try {
          const { toast } = await import("@/components/ui/sonner");
          (toast as any).warning?.("No lineups found in saved run") || toast("No lineups found in saved run");
        } catch {}
        const useRun = useRunStore.getState();
        (useRun as any).reset?.();
        useRunStore.setState({ 
          status: "done", 
          lineups: [], 
          summary: { ...(summary || {}), diagnostics, runId: data?.run_id, slateKey: data?.slate_key }, 
          tried: 0, 
          valid: 0 
        });
      }
      onClose();
    } catch (e) {
      console.error(e);
    }
  };

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 backdrop-blur-sm bg-background/40 flex items-center justify-center">
      <div className="bg-card border rounded w-[720px] max-h-[70vh] p-4 shadow-xl">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium">Load Run</h3>
          <Button variant="outline" size="sm" onClick={onClose} className="hover:bg-destructive/10">Close</Button>
        </div>
        <div className="flex items-end gap-2 mb-3">
          <div className="flex-1">
            <label className="block text-xs text-muted-foreground mb-1">Slate Key (or "all")</label>
            <Input value={slateKey} onChange={(e) => setSlateKey(e.target.value)} placeholder="all" />
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              try {
                const saved = localStorage.getItem("dfs_slate_key");
                if (saved) setSlateKey(saved);
              } catch {}
            }}
          >
            Use Current
          </Button>
          <Button size="sm" onClick={doList} disabled={!canList || loading}>{loading ? "Loading…" : "List"}</Button>
        </div>
        <div className="border rounded h-[42vh] overflow-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="sticky top-0 bg-muted/40">
                <th className="text-left p-2">Run ID</th>
                <th className="text-left p-2">Slate</th>
                <th className="text-left p-2">Created</th>
                <th className="text-left p-2">Tag</th>
                <th className="text-left p-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.run_id} className="border-t">
                  <td className="p-2 font-mono text-[11px]">{r.run_id}</td>
                  <td className="p-2 font-mono text-[11px]">{r.slate_key}</td>
                  <td className="p-2">{formatToEST(r.meta?.created_at)}</td>
                  <td className="p-2">{r.meta?.tag || ""}</td>
                  <td className="p-2">
                    <Button size="sm" variant="outline" onClick={() => onLoad(r.run_id, r.slate_key)}>Load</Button>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td className="p-3 text-muted-foreground" colSpan={5}>No runs found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
