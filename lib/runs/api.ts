export type RunListItem = {
  run_id: string;
  slate_key: string;
  module: string;
  created_at?: string;
  path: string;
  meta?: any;
};

export async function listRuns(module: string, slate: string | undefined, limit = 10): Promise<RunListItem[]> {
  const params = new URLSearchParams({ module, limit: String(limit) });
  if (slate && slate.trim() !== "") params.set("slate", slate);
  else params.set("slate", "all");
  const res = await fetch(`/api/runs?${params.toString()}`);
  const data = await res.json();
  try { if (data?.base) console.debug("[runs] base dir:", data.base); } catch {}
  if (!res.ok || !data?.ok) throw new Error(data?.error || `Failed to list runs (${res.status})`);
  return Array.isArray(data.runs) ? data.runs : [];
}

export async function getRun(slate: string, module: string, run_id: string): Promise<any> {
  const res = await fetch(`/api/runs/${encodeURIComponent(slate)}/${encodeURIComponent(module)}/${encodeURIComponent(run_id)}`);
  const data = await res.json();
  if (!res.ok || !data?.ok) throw new Error(data?.error || `Failed to get run (${res.status})`);
  return data.run;
}

export function currentSlateKeyNY(): string {
  try {
    const fmt = new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York",
      year: "2-digit",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
    const parts = Object.fromEntries(fmt.formatToParts(new Date()).map((p) => [p.type, p.value]));
    const yy = String(parts.year).slice(-2);
    const mm = String(parts.month).padStart(2, "0");
    const dd = String(parts.day).padStart(2, "0");
    const hh = String(parts.hour).padStart(2, "0");
    const mi = String(parts.minute).padStart(2, "0");
    const ss = String(parts.second).padStart(2, "0");
    return `${yy}-${mm}-${dd}_${hh}${mi}${ss}`;
  } catch {
    const d = new Date();
    const yy = String(d.getFullYear()).slice(-2);
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const hh = String(d.getHours()).padStart(2, "0");
    const mi = String(d.getMinutes()).padStart(2, "0");
    const ss = String(d.getSeconds()).padStart(2, "0");
    return `${yy}-${mm}-${dd}_${hh}${mi}${ss}`;
  }
}
