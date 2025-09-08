import { Row, Column } from "@tanstack/react-table";
import { LineupTableData } from "@/lib/table/columns";

/**
 * Exports visible lineup table data to CSV format
 * @param rows - Filtered table rows to export
 * @param columns - Visible columns to include in export
 */
export function exportLineupsToCSV(
  rows: Row<LineupTableData>[],
  columns: Column<LineupTableData>[]
): void {
  if (rows.length === 0) {
    console.warn("No data to export");
    return;
  }

  // Get visible column headers and IDs
  const visibleColumns = columns.filter(col => col.getIsVisible());
  const headers = visibleColumns.map(col => {
    const header = col.columnDef.header;
    return typeof header === "string" ? header : col.id;
  });
  const columnIds = visibleColumns.map(col => col.id);

  // Create CSV content
  const csvRows: string[] = [];
  
  // Add header row
  csvRows.push(headers.map(escapeCSVField).join(","));
  
  // Add data rows
  for (const row of rows) {
    const values = columnIds.map(columnId => {
      const cellValue = row.getValue(columnId);
      return formatCSVValue(cellValue);
    });
    csvRows.push(values.map(escapeCSVField).join(","));
  }

  // Create and download the CSV file
  const csvContent = csvRows.join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  
  // Create download link
  const link = document.createElement("a");
  link.href = url;
  link.download = `lineups-export-${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.csv`;
  link.style.display = "none";
  
  // Trigger download
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  
  // Cleanup
  URL.revokeObjectURL(url);
}

/**
 * Formats a value for CSV export
 */
function formatCSVValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  
  if (typeof value === "number") {
    return value.toString();
  }
  
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  
  if (Array.isArray(value)) {
    return value.join("; ");
  }
  
  return String(value);
}

/**
 * Escapes a field value for CSV format
 */
function escapeCSVField(value: string): string {
  if (!value) return "";
  
  // If the value contains comma, quote, or newline, wrap in quotes and escape quotes
  if (value.includes(",") || value.includes('"') || value.includes("\n")) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  
  return value;
}