// Small alias maps for DK quirks and normalization helpers

export const TEAM_ALIASES: Record<string, string> = {
  NO: "NOP",
  NOP: "NOP",
  PHO: "PHX",
  PHX: "PHX",
  SA: "SAS",
  SAS: "SAS",
};

export function normalizeTeam(team: string): string {
  const t = team.trim().toUpperCase();
  return TEAM_ALIASES[t] ?? t;
}

export function normalizeNameKey(name: string): string {
  // Uppercase, remove periods and extra spaces, collapse whitespace
  return name
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "") // strip diacritics
    .toUpperCase()
    .replace(/\./g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function splitPositions(pos: string | null | undefined): [string, string | null] {
  if (!pos) return ["", null];
  const parts = String(pos)
    .toUpperCase()
    .split("/")
    .map((s) => s.trim())
    .filter(Boolean);
  const primary = parts[0] ?? "";
  const secondary = parts.length > 1 ? parts[1] : null;
  return [primary, secondary];
}

