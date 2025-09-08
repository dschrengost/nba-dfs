"use client";

import * as React from "react";
import { Table as TableType } from "@tanstack/react-table";
import { Search, Settings, Download, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LineupTableData } from "@/lib/table/columns";
import { exportLineupsToCSV } from "@/lib/csv/exportLineups";

interface LineupToolbarProps {
  table: TableType<LineupTableData>;
  globalFilter: string;
  setGlobalFilter: (value: string) => void;
  data: LineupTableData[];
}

export function LineupToolbar({
  table,
  globalFilter,
  setGlobalFilter,
  data,
}: LineupToolbarProps) {
  const visibleRowCount = table.getFilteredRowModel().rows.length;
  const totalRowCount = data.length;

  const handleExportCSV = () => {
    const visibleColumns = table.getAllColumns().filter(col => col.getIsVisible());
    const visibleRows = table.getFilteredRowModel().rows;
    exportLineupsToCSV(visibleRows, visibleColumns);
  };

  const handleReset = () => {
    setGlobalFilter("");
    table.resetColumnFilters();
    table.resetColumnVisibility();
    table.resetColumnPinning();
    table.resetSorting();
  };

  const handleColumnPin = (columnId: string) => {
    const currentPinning = table.getState().columnPinning;
    const isCurrentlyPinned = currentPinning.left?.includes(columnId);
    
    if (isCurrentlyPinned) {
      // Unpin column
      table.setColumnPinning({
        ...currentPinning,
        left: currentPinning.left?.filter(id => id !== columnId) || [],
      });
    } else {
      // Pin column to left
      table.setColumnPinning({
        ...currentPinning,
        left: [...(currentPinning.left || []), columnId],
      });
    }
  };

  return (
    <div className="flex items-center justify-between gap-3 py-1">
      {/* Left side: Search and Column Management */}
      <div className="flex items-center gap-3">
        <div className="relative">
          <Search className="absolute left-2 top-2 h-3 w-3 text-muted-foreground" />
          <Input
            placeholder="Search players..."
            value={globalFilter ?? ""}
            onChange={(e) => setGlobalFilter(e.target.value)}
            className="pl-7 h-8 w-48 text-xs"
            data-testid="lineup-search-input"
          />
        </div>
        
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="h-8 px-2 text-xs"
              data-testid="column-settings-button"
            >
              <Settings className="mr-1 h-3 w-3" />
              Columns
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-[200px]">
            <DropdownMenuLabel>Toggle Columns</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {table
              .getAllColumns()
              .filter((column) => column.getCanHide())
              .map((column) => {
                const isPinned = table.getState().columnPinning.left?.includes(column.id);
                return (
                  <div key={column.id}>
                    <DropdownMenuCheckboxItem
                      className="capitalize"
                      checked={column.getIsVisible()}
                      onCheckedChange={(value) => column.toggleVisibility(!!value)}
                      data-testid={`column-toggle-${column.id}`}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span>{column.columnDef.header as string}</span>
                        {isPinned && (
                          <Badge variant="secondary" className="text-xs">
                            Pinned
                          </Badge>
                        )}
                      </div>
                    </DropdownMenuCheckboxItem>
                    {column.getIsVisible() && (
                      <DropdownMenuCheckboxItem
                        className="pl-6 text-xs"
                        checked={isPinned}
                        onCheckedChange={() => handleColumnPin(column.id)}
                        data-testid={`column-pin-${column.id}`}
                      >
                        Pin to left
                      </DropdownMenuCheckboxItem>
                    )}
                  </div>
                );
              })}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Right side: Export, Reset, and Row Count */}
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="text-xs px-2 py-1 font-mono" data-testid="row-count-badge">
          {visibleRowCount === totalRowCount 
            ? `${totalRowCount} rows`
            : `${visibleRowCount} of ${totalRowCount} rows`
          }
        </Badge>
        
        <Button
          variant="outline"
          size="sm"
          onClick={handleExportCSV}
          disabled={visibleRowCount === 0}
          className="h-8 px-2 text-xs"
          data-testid="export-csv-button"
        >
          <Download className="mr-1 h-3 w-3" />
          Export CSV
        </Button>
        
        <Button
          variant="outline"
          size="sm"
          onClick={handleReset}
          className="h-8 px-2 text-xs"
          data-testid="reset-button"
        >
          <RotateCcw className="mr-1 h-3 w-3" />
          Reset
        </Button>
      </div>
    </div>
  );
}