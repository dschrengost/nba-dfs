import { ColumnDef } from "@tanstack/react-table";
import { Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useRosterMap, type PlayerInfo } from "@/hooks/useRosterMap";

// Extended lineup type with additional metrics from PRP requirements
export interface LineupTableData {
  lineup_id: string;
  score: number;
  salary_used: number;
  salary_left?: number;
  dup_risk?: number;
  own_sum?: number;
  own_avg?: number;
  lev_sum?: number;
  lev_avg?: number;
  num_uniques_in_pool?: number;
  teams_used?: string[] | number;
  proj_pts_sum?: number;
  stack_flags?: string;
  
  // Player slots
  PG?: string;
  SG?: string;
  SF?: string;
  PF?: string;
  C?: string;
  G?: string;
  F?: string;
  UTIL?: string;
}

// Copy ID button component
const CopyIdButton = ({ playerId }: { playerId: string }) => {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(playerId);
      // Could add toast notification here
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  return (
    <Button
      variant="ghost"
      size="sm"
      className="h-4 w-4 p-0 ml-1"
      onClick={handleCopy}
      data-testid={`copy-player-${playerId}`}
    >
      <Copy className="h-3 w-3" />
      <span className="sr-only">Copy player ID</span>
    </Button>
  );
};

// Player cell component with name and ID
const PlayerCell = ({ playerId, playerInfo }: { playerId: string; playerInfo?: PlayerInfo }) => {
  const displayName = playerInfo?.name || "";
  const hasName = displayName && displayName.trim().length > 0;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="text-left" data-testid={`player-cell-${playerId}`}>
          {hasName ? (
            <>
              <div className="font-medium truncate">{displayName}</div>
              <div className="text-xs text-muted-foreground flex items-center">
                ({playerId})
                <CopyIdButton playerId={playerId} />
              </div>
            </>
          ) : (
            <div className="font-medium flex items-center">
              {playerId}
              <CopyIdButton playerId={playerId} />
            </div>
          )}
        </div>
      </TooltipTrigger>
      <TooltipContent>
        <div>
          {hasName ? (
            <>
              <p className="font-medium">{displayName}</p>
              <p className="text-xs text-muted-foreground">
                {playerInfo?.team && playerInfo?.pos ? `${playerInfo.team} - ${playerInfo.pos}` : ""}
              </p>
              <p className="text-xs">ID: {playerId}</p>
            </>
          ) : (
            <p>Player ID: {playerId}<br />Name unavailable</p>
          )}
        </div>
      </TooltipContent>
    </Tooltip>
  );
};

// Number formatters
const formatScore = (value: number) => 
  new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);

const formatSalary = (value: number) => 
  new Intl.NumberFormat("en-US").format(value);

const formatPercentage = (value: number) => 
  new Intl.NumberFormat("en-US", { style: "percent", minimumFractionDigits: 1 }).format(value);

const formatDecimal3 = (value: number) => 
  new Intl.NumberFormat("en-US", { minimumFractionDigits: 3, maximumFractionDigits: 3 }).format(value);

export const createLineupColumns = (rosterMap: Record<string, PlayerInfo> = {}): ColumnDef<LineupTableData>[] => [
  {
    accessorKey: "lineup_id",
    header: "ID",
    size: 80,
    cell: ({ getValue }) => (
      <div className="font-mono text-xs" data-testid="lineup-id-cell">
        {String(getValue()).slice(-8)}
      </div>
    ),
  },
  {
    accessorKey: "score",
    header: "Score",
    size: 80,
    cell: ({ getValue }) => (
      <div className="font-mono tabular-nums text-right" data-testid="score-cell">
        {formatScore(Number(getValue()))}
      </div>
    ),
  },
  {
    accessorKey: "salary_used",
    header: "Salary",
    size: 80,
    cell: ({ getValue }) => (
      <div className="font-mono tabular-nums text-right" data-testid="salary-cell">
        {formatSalary(Number(getValue()))}
      </div>
    ),
  },
  {
    accessorKey: "salary_left",
    header: "Left",
    size: 60,
    cell: ({ getValue }) => {
      const value = getValue();
      return (
        <div className="font-mono tabular-nums text-right text-xs" data-testid="salary-left-cell">
          {value !== undefined ? formatSalary(Number(value)) : "—"}
        </div>
      );
    },
  },
  {
    accessorKey: "dup_risk",
    header: "Dup Risk",
    size: 80,
    cell: ({ getValue }) => {
      const value = getValue();
      return (
        <div className="font-mono tabular-nums text-right" data-testid="dup-risk-cell">
          {value !== undefined ? formatPercentage(Number(value)) : "—"}
        </div>
      );
    },
  },
  {
    accessorKey: "own_avg",
    header: "Own %",
    size: 80,
    cell: ({ getValue, row }) => {
      const avg = getValue();
      // Avoid accessing a non-declared column via row.getValue("own_sum").
      // Read directly from the original row to prevent console errors.
      const raw: any = row.original as any;
      const sum = raw?.own_sum;
      const value = avg !== undefined ? avg : sum !== undefined ? Number(sum) / 8 : undefined;
      return (
        <div className="font-mono tabular-nums text-right" data-testid="ownership-cell">
          {value !== undefined ? formatPercentage(Number(value)) : "—"}
        </div>
      );
    },
  },
  {
    accessorKey: "num_uniques_in_pool",
    header: "Uniques",
    size: 80,
    cell: ({ getValue }) => {
      const value = getValue();
      return (
        <div className="font-mono tabular-nums text-right" data-testid="uniques-cell">
          {value !== undefined ? formatSalary(Number(value)) : "—"}
        </div>
      );
    },
  },
  {
    accessorKey: "teams_used",
    header: "Teams",
    size: 60,
    cell: ({ getValue }) => {
      const value = getValue();
      let count: number;
      let teamsList: string[] = [];

      if (Array.isArray(value)) {
        count = value.length;
        teamsList = value;
      } else if (typeof value === "number") {
        count = value;
      } else {
        count = 0;
      }

      return (
        <Tooltip>
          <TooltipTrigger>
            <div className="font-mono tabular-nums text-right cursor-default" data-testid="teams-cell">
              {count}
            </div>
          </TooltipTrigger>
          <TooltipContent>
            <p>{teamsList.length > 0 ? `Teams: ${teamsList.join(", ")}` : `${count} teams used`}</p>
          </TooltipContent>
        </Tooltip>
      );
    },
  },
  // Player position columns
  {
    accessorKey: "PG",
    header: "PG",
    size: 140,
    cell: ({ getValue }) => {
      const playerId = String(getValue() || "");
      return playerId ? <PlayerCell playerId={playerId} playerInfo={rosterMap[playerId]} /> : null;
    },
  },
  {
    accessorKey: "SG", 
    header: "SG",
    size: 140,
    cell: ({ getValue }) => {
      const playerId = String(getValue() || "");
      return playerId ? <PlayerCell playerId={playerId} playerInfo={rosterMap[playerId]} /> : null;
    },
  },
  {
    accessorKey: "SF",
    header: "SF", 
    size: 140,
    cell: ({ getValue }) => {
      const playerId = String(getValue() || "");
      return playerId ? <PlayerCell playerId={playerId} playerInfo={rosterMap[playerId]} /> : null;
    },
  },
  {
    accessorKey: "PF",
    header: "PF",
    size: 140,
    cell: ({ getValue }) => {
      const playerId = String(getValue() || "");
      return playerId ? <PlayerCell playerId={playerId} playerInfo={rosterMap[playerId]} /> : null;
    },
  },
  {
    accessorKey: "C",
    header: "C",
    size: 140,
    cell: ({ getValue }) => {
      const playerId = String(getValue() || "");
      return playerId ? <PlayerCell playerId={playerId} playerInfo={rosterMap[playerId]} /> : null;
    },
  },
  {
    accessorKey: "G",
    header: "G",
    size: 140,
    cell: ({ getValue }) => {
      const playerId = String(getValue() || "");
      return playerId ? <PlayerCell playerId={playerId} playerInfo={rosterMap[playerId]} /> : null;
    },
  },
  {
    accessorKey: "F",
    header: "F",
    size: 140,
    cell: ({ getValue }) => {
      const playerId = String(getValue() || "");
      return playerId ? <PlayerCell playerId={playerId} playerInfo={rosterMap[playerId]} /> : null;
    },
  },
  {
    accessorKey: "UTIL",
    header: "UTIL",
    size: 140,
    cell: ({ getValue }) => {
      const playerId = String(getValue() || "");
      return playerId ? <PlayerCell playerId={playerId} playerInfo={rosterMap[playerId]} /> : null;
    },
  },
];
