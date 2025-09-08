"use client";

import { useMemo } from "react";

export interface PlayerInfo {
  name?: string;
  team?: string;
  pos?: string;
}

export type RosterMap = Record<string, PlayerInfo>;

interface RosterMapOptions {
  playerMap?: RosterMap;
  lineups?: Array<{
    slots?: Array<{
      player_id_dk?: string;
      name?: string;
      team?: string;
      pos?: string;
    }>;
  }>;
  runId?: string;
}

const rosterMapCache = new Map<string, RosterMap>();

export function useRosterMap(options: RosterMapOptions = {}): {
  getRosterMap: () => RosterMap;
  getPlayerInfo: (playerId: string) => PlayerInfo | undefined;
  hasPlayerName: (playerId: string) => boolean;
} {
  const { playerMap, lineups, runId } = options;

  const memoizedRosterMap = useMemo(() => {
    const cacheKey = runId || "default";

    // Start from any existing cache, but always merge fresh data to avoid stale names
    const base = rosterMapCache.get(cacheKey) || {};
    const rosterMap: RosterMap = { ...base };

    if (playerMap) {
      Object.assign(rosterMap, playerMap);
    }

    if (lineups?.length) {
      for (const lineup of lineups) {
        if (!lineup?.slots?.length) continue;
        for (const slot of lineup.slots) {
          const pid = slot?.player_id_dk;
          if (!pid) continue;
          const current = rosterMap[pid];
          const incoming: PlayerInfo = {
            name: slot?.name ?? current?.name,
            team: slot?.team ?? current?.team,
            pos: slot?.pos ?? current?.pos,
          };
          // Write if new or adds a name/team/pos we didn't have
          if (!current || !current.name || !current.team || !current.pos) {
            rosterMap[pid] = incoming;
          }
        }
      }
    }

    rosterMapCache.set(cacheKey, rosterMap);
    return rosterMap;
  }, [playerMap, lineups, runId]);

  const getRosterMap = () => memoizedRosterMap;

  const getPlayerInfo = (playerId: string): PlayerInfo | undefined => {
    return memoizedRosterMap[playerId];
  };

  const hasPlayerName = (playerId: string): boolean => {
    const info = memoizedRosterMap[playerId];
    return Boolean(info?.name && info.name.trim().length > 0);
  };

  return {
    getRosterMap,
    getPlayerInfo,
    hasPlayerName,
  };
}
