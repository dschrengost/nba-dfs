# Lib Module (Shared Utilities)

The lib module provides shared TypeScript utilities, domain types, and common functionality used across the Next.js frontend and integration layers. It serves as the bridge between the React UI and the Python backend processes.

## Overview

The lib module contains:
- **Domain Models**: TypeScript types for DFS entities (players, lineups, projections)
- **State Management**: Zustand stores for application state
- **Data Processing**: CSV parsing, validation, and transformation utilities
- **Integration Adapters**: Frontend adapters for backend processes
- **UI Utilities**: Common UI helpers, constants, and accessibility functions
- **Algorithm Implementations**: Client-side optimization algorithms

## Architecture

```
lib/
├── domain/             # Core domain types and models
├── state/              # Zustand state management stores
├── ingest/             # Data ingestion and parsing utilities
├── opt/                # Optimization algorithms and utilities
├── runs/               # Run management and tracking
├── csv/                # CSV processing and export utilities
├── table/              # Data table utilities and configurations
├── ui/                 # UI helpers, constants, and accessibility
└── utils.ts            # General utility functions
```

## Core Components

### 1. Domain Types (`lib/domain/`)
**Purpose**: Define TypeScript interfaces for all DFS domain entities

**Core Types:**
```typescript
// Player entity
type Player = {
  player_id_dk: string;      // DraftKings player ID
  player_name: string;       // Display name
  team: string;              // 3-letter team code
  pos_primary: string;       // Primary position (PG, SG, etc.)
  pos_secondary?: string;    // Secondary position (optional)
};

// Projection data
type Projection = {
  player_id_dk: string;      // Links to Player
  salary: number;            // DK salary (integer)
  proj_fp: number;           // Projected fantasy points
  mins?: number;             // Projected minutes
  ownership?: number;        // Projected ownership % 
  ceiling?: number;          // Ceiling projection
  floor?: number;            // Floor projection
  source: string;            // Projection source identifier
  version_ts?: string;       // Timestamp (ISO string)
};

// Combined player + projection
type MergedPlayer = Player & Projection;

// Lineup representation
type Lineup = {
  lineup_id: string;
  players: string[];         // Array of 8 dk_player_ids
  total_salary: number;
  proj_fp: number;
  export_csv_row: string;    // DK-formatted lineup string
};
```

**Features:**
- **Strict Typing**: All entities use exact TypeScript interfaces
- **Schema Alignment**: Types match Python pipeline schemas exactly
- **Export Ready**: Include DraftKings formatting specifications

### 2. State Management (`lib/state/`)
**Purpose**: Zustand stores for application-wide state management

#### Ingest Store (`ingest-store.ts`)
```typescript
type IngestState = {
  // File upload state
  uploadedFiles: UploadedFile[];
  uploadProgress: Record<string, number>;
  
  // Parsing state
  parsedPlayers: Player[];
  parsedProjections: Projection[];
  mergedData: MergedPlayer[];
  
  // Validation state
  validationErrors: ValidationError[];
  duplicateHandling: 'keep-first' | 'keep-last' | 'manual';
  
  // Actions
  addFile: (file: File, type: FileType) => void;
  parseCSV: (file: File) => Promise<ParseResult>;
  validateData: () => ValidationResult;
  mergePlayers: () => MergedPlayer[];
};
```

#### Run Store (`run-store.ts`)
```typescript
type RunState = {
  // Active runs tracking
  activeRuns: ActiveRun[];
  runHistory: RunSummary[];
  selectedRun?: string;
  
  // Run management
  startRun: (config: RunConfig) => Promise<string>;
  pollRunStatus: (runId: string) => Promise<RunStatus>;
  loadRunResults: (runId: string) => Promise<RunResults>;
  
  // Results caching
  cachedResults: Record<string, RunResults>;
  cacheTimeout: number;
};
```

**Features:**
- **Reactive Updates**: Automatic UI updates on state changes
- **Persistence**: Local storage integration for form state
- **Optimistic Updates**: Immediate UI feedback with rollback on errors

### 3. Data Ingestion (`lib/ingest/`)
**Purpose**: Frontend data parsing, validation, and normalization

#### CSV Parsing (`parse.ts`)
```typescript
// Parse CSV files with validation
async function parseCSV<T>(
  file: File, 
  schema: ZodSchema<T>,
  options?: ParseOptions
): Promise<ParseResult<T>> {
  // Papa Parse integration with streaming
  // Real-time validation with Zod schemas
  // Error collection and reporting
}

// Normalize column headers
function normalizeHeaders(
  headers: string[], 
  mapping: HeaderMapping
): string[] {
  // Case-insensitive matching
  // Alias resolution
  // Missing field detection
}
```

#### Schema Validation (`schemas.ts`)
```typescript
// Zod schemas matching Python pipeline schemas
const PlayerSchema = z.object({
  player_id_dk: z.string().min(1),
  player_name: z.string().min(1),
  team: z.string().length(3),
  pos_primary: z.enum(['PG', 'SG', 'SF', 'PF', 'C']),
  pos_secondary: z.enum(['G', 'F', 'UTIL']).optional()
});

const ProjectionSchema = z.object({
  player_id_dk: z.string().min(1),
  salary: z.number().int().min(3000).max(11000),
  proj_fp: z.number().min(0),
  mins: z.number().min(0).max(48).optional(),
  ownership: z.number().min(0).max(1).optional()
});
```

### 4. Optimization (`lib/opt/`)
**Purpose**: Client-side optimization algorithms and utilities

#### Greedy Algorithm (`algorithms/greedy.ts`)
```typescript
// Fallback optimization when Python solver unavailable
function greedyOptimize(
  players: MergedPlayer[],
  config: OptimizerConfig
): Lineup[] {
  // Value-based greedy selection
  // Constraint satisfaction
  // Multiple lineup generation
}

// Constraint validation
function validateLineup(
  lineup: Lineup,
  constraints: Constraints
): ValidationResult {
  // Position requirements
  // Salary cap compliance
  // Team limits
}
```

**Features:**
- **Fallback Optimization**: Client-side solver when backend unavailable
- **Constraint Engine**: Full DK constraint validation
- **Performance**: Optimized for browser execution

### 5. Run Management (`lib/runs/`)
**Purpose**: Integration with backend run system

```typescript
// Run discovery and tracking
async function findRuns(
  slateId: string,
  runType?: RunType
): Promise<RunSummary[]> {
  // Query run registry
  // Filter and sort results
  // Return metadata summaries
}

// Run execution interface
async function executeRun(
  process: ProcessType,
  config: ProcessConfig
): Promise<RunHandle> {
  // Start backend process
  // Return polling handle
  // Handle error states
}
```

### 6. CSV Export (`lib/csv/`)
**Purpose**: Export lineup data in DraftKings format

```typescript
// Generate DK-compatible CSV
function exportLineups(
  lineups: Lineup[],
  format: 'dk' | 'fd' | 'sb'
): string {
  // Format player names for platform
  // Correct position ordering
  // Include required metadata
}

// Batch export with validation
function exportLineupsToFile(
  lineups: Lineup[],
  filename: string,
  options: ExportOptions
): void {
  // Client-side file generation
  // Automatic download trigger
  // Error handling and validation
}
```

### 7. UI Utilities (`lib/ui/`)
**Purpose**: Common UI helpers and accessibility functions

#### Accessibility (`a11y.ts`)
```typescript
// Motion preference detection
function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

// Screen reader utilities
function announceToScreenReader(message: string): void {
  // Live region updates
  // Polite vs assertive announcements
}
```

#### Constants (`constants.ts`)
```typescript
// UI timing constants
export const SKELETON_MS = 800;
export const DEBOUNCE_MS = 300;
export const TOAST_DURATION = 4000;

// Animation durations
export const MOTION = {
  FAST: 150,
  DEFAULT: 250,
  SLOW: 500
} as const;
```

#### Layout Utilities (`layout.ts`)
```typescript
// Responsive breakpoint utilities
function useBreakpoint(): Breakpoint {
  // Window size detection
  // Responsive state management
}

// Grid layout calculations
function calculateGridColumns(
  containerWidth: number,
  itemWidth: number,
  gap: number
): number {
  // Responsive grid column count
  // Account for gaps and padding
}
```

### 8. Table Utilities (`lib/table/`)
**Purpose**: Data table configurations and utilities

```typescript
// Column definitions for different data types
const LINEUP_COLUMNS: ColumnDef<Lineup>[] = [
  {
    id: 'players',
    header: 'Players',
    cell: ({ row }) => <PlayerCell lineup={row.original} />
  },
  {
    id: 'salary',
    header: 'Salary',
    cell: ({ row }) => formatCurrency(row.original.total_salary)
  }
];

// Table state management
function useTableState<T>(data: T[]) {
  // Sorting, filtering, pagination
  // Column visibility controls
  // Export functionality
}
```

## Integration Patterns

### Backend Communication
The lib module provides consistent patterns for backend integration:

```typescript
// File system integration
async function readParquetFile(path: string): Promise<DataFrame> {
  // Read parquet via API endpoint
  // Parse and validate data
  // Return typed results
}

// Process execution
async function runPythonProcess(
  module: string,
  args: ProcessArgs
): Promise<ProcessResult> {
  // Execute Python CLI command
  // Stream progress updates
  // Handle success/error states
}
```

### Error Handling
```typescript
// Consistent error types
type ProcessError = {
  code: 'VALIDATION_ERROR' | 'PROCESS_ERROR' | 'FILE_ERROR';
  message: string;
  details?: Record<string, any>;
};

// Error boundary integration
function handleProcessError(error: ProcessError): void {
  // Log error details
  // Show user-friendly message
  // Trigger error reporting
}
```

## Testing

### Unit Tests (`__tests__/`)
```typescript
// Example ingest test
describe('CSV Parsing', () => {
  it('should parse valid projections CSV', async () => {
    const file = createTestFile(validProjectionsCSV);
    const result = await parseCSV(file, ProjectionSchema);
    
    expect(result.success).toBe(true);
    expect(result.data).toHaveLength(3);
    expect(result.data[0].player_id_dk).toBe('12345');
  });
});
```

### Integration Tests
```typescript
// End-to-end workflow testing
describe('Optimization Workflow', () => {
  it('should complete full optimization cycle', async () => {
    // Upload files
    const players = await uploadPlayers(testPlayerData);
    
    // Run optimization
    const runId = await startOptimization(testConfig);
    
    // Wait for completion
    const result = await pollUntilComplete(runId);
    
    // Validate outputs
    expect(result.lineups).toHaveLength(5);
    expect(result.lineups[0].players).toHaveLength(8);
  });
});
```

## Dependencies

### Core Dependencies
```json
{
  "zustand": "^5.0.8",           // State management
  "zod": "^3.25.76",             // Schema validation
  "papaparse": "^5.5.3"         // CSV parsing
}
```

### Dev Dependencies
```json
{
  "vitest": "^3.2.4",           // Testing framework  
  "@types/papaparse": "*"       // TypeScript definitions
}
```

## Performance Considerations

### Optimization Strategies
- **Lazy Loading**: Dynamic imports for heavy algorithms
- **Memoization**: Cache expensive calculations with useMemo
- **Streaming**: Process large CSV files in chunks
- **Web Workers**: Offload CPU-intensive tasks

### Memory Management
```typescript
// Efficient data processing
function processLargeDataset<T>(
  data: T[],
  batchSize: number = 1000
): Promise<T[]> {
  // Process in batches to avoid memory spikes
  // Yield control between batches
  // Report progress for user feedback
}
```

## Future Enhancements

### Planned Features
- **Web Workers**: Background processing for optimization
- **IndexedDB**: Client-side data persistence
- **Streaming**: Real-time data processing
- **Service Worker**: Offline functionality

### Performance Improvements
- **Virtual Scrolling**: Handle massive datasets efficiently
- **Incremental Loading**: Load data on demand
- **Compression**: Reduce data transfer sizes
- **Caching**: Intelligent result caching strategies