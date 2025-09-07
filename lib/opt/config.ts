import type { Slot } from "@/lib/opt/types";

export const DEFAULT_SALARY_CAP = 50000;
export const DEFAULT_SLOTS: Slot[] = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"];
export const DEFAULT_MAX_PER_TEAM = 3;

export const DEFAULT_FIXTURE_DATE = "2024-01-15"; // YYYY-MM-DD
export const USE_FIXTURE_FALLBACK = true;
export const DEFAULT_SEED = `dk-fixture-${DEFAULT_FIXTURE_DATE}`;

