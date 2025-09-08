"use client";

import * as React from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  SortingState,
  ColumnFiltersState,
  VisibilityState,
  ColumnPinningState,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { LineupTableData, createLineupColumns } from "@/lib/table/columns";
import { useRosterMap } from "@/hooks/useRosterMap";
import { LineupToolbar } from "./LineupToolbar";

interface LineupTableProps {
  data: LineupTableData[];
  playerMap?: Record<string, { name?: string; team?: string; pos?: string }>;
  lineups?: Array<{
    slots?: Array<{
      player_id_dk?: string;
      name?: string;
      team?: string;
      pos?: string;
    }>;
  }>;
  runId?: string;
  className?: string;
}

export function LineupTable({ 
  data, 
  playerMap, 
  lineups,
  runId, 
  className 
}: LineupTableProps) {
  const [sorting, setSorting] = React.useState<SortingState>([
    { id: "score", desc: true }, // Default sort by score descending
  ]);
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>({});
  const [columnPinning, setColumnPinning] = React.useState<ColumnPinningState>({});
  const [globalFilter, setGlobalFilter] = React.useState("");

  // Get roster map for player info
  const { getRosterMap } = useRosterMap({ 
    playerMap, 
    lineups,
    runId 
  });
  const rosterMap = getRosterMap();

  // Create columns with roster map
  const columns = React.useMemo(() => createLineupColumns(rosterMap), [rosterMap]);

  // Table instance
  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      columnPinning,
      globalFilter,
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onColumnPinningChange: setColumnPinning,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: {
        pageSize: 10000, // Show all rows
      },
    },
  });

  // Virtualization for large datasets (>1,500 rows)
  const parentRef = React.useRef<HTMLDivElement>(null);
  const shouldVirtualize = data.length > 1500;

  const rowVirtualizer = useVirtualizer({
    count: shouldVirtualize ? table.getRowModel().rows.length : 0,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 32, // Estimated row height
    overscan: 10,
  });

  // Local storage persistence for column settings
  const storageKey = React.useMemo(() => `lineup-table-settings-${runId || "default"}`, [runId]);

  React.useEffect(() => {
    const saved = localStorage.getItem(storageKey);
    if (saved) {
      try {
        const { visibility, pinning } = JSON.parse(saved);
        if (visibility) setColumnVisibility(visibility);
        if (pinning) setColumnPinning(pinning);
      } catch (error) {
        console.error("Failed to load table settings:", error);
      }
    }
  }, [storageKey]);

  React.useEffect(() => {
    const settings = {
      visibility: columnVisibility,
      pinning: columnPinning,
    };
    localStorage.setItem(storageKey, JSON.stringify(settings));
  }, [columnVisibility, columnPinning, storageKey]);

  return (
    <TooltipProvider>
      <Card className={`${className} bg-card/50 backdrop-blur-sm`} data-testid="lineup-table-card">
        <CardHeader className="pb-3">
          <LineupToolbar 
            table={table}
            globalFilter={globalFilter}
            setGlobalFilter={setGlobalFilter}
            data={data}
          />
        </CardHeader>
        <CardContent className="p-0">
          <div 
            ref={parentRef}
            className="relative overflow-auto border-t custom-scrollbar"
            style={{ height: shouldVirtualize ? "600px" : "400px", maxHeight: "60vh" }}
          >
            <Table>
              <TableHeader className="sticky top-0 z-10 bg-background/95 backdrop-blur-sm border-b">
                {table.getHeaderGroups().map((headerGroup) => (
                  <TableRow key={headerGroup.id} className="hover:bg-transparent">
                    {headerGroup.headers.map((header) => (
                      <TableHead 
                        key={header.id}
                        style={{ width: header.getSize() }}
                        className="text-xs font-semibold h-7 px-2 py-1"
                        data-testid={`header-${header.id}`}
                      >
                        {header.isPlaceholder ? null : (
                          <div
                            className={
                              header.column.getCanSort()
                                ? "cursor-pointer select-none flex items-center gap-1 hover:text-primary transition-colors"
                                : "flex items-center gap-1"
                            }
                            onClick={header.column.getToggleSortingHandler()}
                          >
                            {flexRender(
                              header.column.columnDef.header,
                              header.getContext()
                            )}
                            {{
                              asc: " ↑",
                              desc: " ↓",
                            }[header.column.getIsSorted() as string] ?? null}
                          </div>
                        )}
                      </TableHead>
                    ))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {shouldVirtualize ? (
                  // Virtualized rows for large datasets
                  <>
                    <tr style={{ height: rowVirtualizer.getTotalSize() }}>
                      <td />
                    </tr>
                    {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                      const row = table.getRowModel().rows[virtualRow.index];
                      if (!row) return null;
                      
                      return (
                        <TableRow
                          key={row.id}
                          data-state={row.getIsSelected() && "selected"}
                          className="hover:bg-muted/30 transition-colors h-8 border-b border-border/50"
                          style={{
                            position: "absolute",
                            top: 0,
                            left: 0,
                            width: "100%",
                            height: virtualRow.size,
                            transform: `translateY(${virtualRow.start}px)`,
                          }}
                          data-testid={`table-row-${virtualRow.index}`}
                        >
                          {row.getVisibleCells().map((cell) => (
                            <TableCell 
                              key={cell.id}
                              style={{ width: cell.column.getSize() }}
                              className="text-xs py-1 px-2 font-medium"
                              data-testid={`cell-${cell.column.id}`}
                            >
                              {flexRender(
                                cell.column.columnDef.cell,
                                cell.getContext()
                              )}
                            </TableCell>
                          ))}
                        </TableRow>
                      );
                    })}
                  </>
                ) : (
                  // Regular rows for smaller datasets
                  table.getRowModel().rows.length > 0 ? (
                    table.getRowModel().rows.map((row, index) => (
                      <TableRow
                        key={row.id}
                        data-state={row.getIsSelected() && "selected"}
                        className="hover:bg-muted/30 transition-colors h-8 border-b border-border/50"
                        data-testid={`table-row-${index}`}
                      >
                        {row.getVisibleCells().map((cell) => (
                          <TableCell 
                            key={cell.id}
                            style={{ width: cell.column.getSize() }}
                            className="text-xs py-1 px-2 font-medium"
                            data-testid={`cell-${cell.column.id}`}
                          >
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext()
                            )}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell
                        colSpan={columns.length}
                        className="h-16 text-center text-muted-foreground"
                        data-testid="no-results-cell"
                      >
                        No results found.
                      </TableCell>
                    </TableRow>
                  )
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </TooltipProvider>
  );
}