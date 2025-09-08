# App Module (Next.js Frontend)

The app module provides the unified dashboard and user interface for the NBA-DFS pipeline, built with Next.js 14 and React 18. It serves as the primary interaction layer for data upload, optimization configuration, and results visualization.

## Overview

The app module implements a modern web application that provides:
- **Interactive Studio**: Visual interface for all DFS pipeline stages
- **Data Upload**: CSV file ingestion with validation and preview
- **Configuration Management**: Visual forms for optimizer and pipeline settings  
- **Results Visualization**: Tables, charts, and analytics for pipeline outputs
- **Real-time Updates**: Live progress tracking for long-running processes
- **API Integration**: RESTful endpoints for backend process orchestration

## Architecture

```
app/
├── (studio)/           # Main application pages
│   ├── optimizer/      # Optimization interface
│   ├── variants/       # Variant generation UI
│   ├── field/          # Field sampling interface
│   └── simulator/      # GPP simulation dashboard
├── api/                # Next.js API routes
│   ├── optimize/       # Optimization endpoints
│   └── runs/           # Run management endpoints
├── layout.tsx          # Root application layout
├── page.tsx            # Landing page
└── icon.svg            # Application icon
```

## User Interface Structure

### Studio Layout
The main application uses a tabbed interface with consistent layout:

```tsx
<TopStatusBar />           // System status and notifications
<TopTabs />               // Navigation: Optimizer | Variants | Field | Simulator  
<Separator />
<PageContainer>           // Main content area with controls
  {children}              // Stage-specific UI components
</PageContainer>
<MetricsDrawer />         // Collapsible analytics panel
```

### Theme System
- **Provider**: `next-themes` with system preference detection
- **Modes**: Light, dark, and system automatic switching
- **Components**: Consistent theming across all UI elements
- **Accessibility**: WCAG compliant color contrast

## Core Features

### 1. Data Upload & Ingestion
**Location**: Upload components integrated across all stages

**Features:**
- **Drag & Drop**: File upload with visual feedback
- **CSV Validation**: Real-time parsing and schema validation
- **Preview**: Data table preview with column mapping
- **Progress**: Upload progress with error handling
- **Batch Processing**: Multiple file upload support

**Supported Formats:**
- Player projections CSV
- Player IDs CSV  
- Contest structure files
- Configuration YAML files

### 2. Optimizer Interface (`app/(studio)/optimizer/`)
**Purpose**: Configure and run lineup optimization

**UI Components:**
- **Configuration Panel**: Salary caps, position rules, stacking options
- **Constraint Builder**: Visual constraint configuration
- **Live Progress**: Real-time optimization status
- **Results Grid**: Lineup table with sorting and filtering
- **Export Controls**: CSV download and formatting options

**Key Features:**
```tsx
// Configuration form with real-time validation
<OptimizerConfig 
  onConfigChange={handleConfigUpdate}
  validation={configErrors}
/>

// Results visualization with interactive tables
<LineupViews 
  lineups={optimizedLineups}
  metrics={optimizationMetrics}
/>
```

### 3. Variants Interface (`app/(studio)/variants/`)
**Purpose**: Generate and manage lineup variants

**Features:**
- **Source Selection**: Choose base lineups from optimizer runs
- **Variant Settings**: Configure generation parameters
- **Catalog View**: Browse generated variant lineups
- **Comparison Tools**: Compare variants against base lineups

### 4. Field Sampling Interface (`app/(studio)/field/`)
**Purpose**: Build representative contest fields

**Features:**
- **Field Configuration**: Contest size, ownership curves, source mix
- **Sampling Preview**: Live field composition updates
- **Diversity Metrics**: Field overlap and uniqueness analytics
- **Export Ready**: Contest-ready field downloads

### 5. Simulator Dashboard (`app/(studio)/simulator/`)
**Purpose**: Run GPP simulations and analyze expected value

**Features:**
- **Contest Setup**: Prize structure, field size, entry fees
- **Simulation Controls**: Monte Carlo parameters, variance models
- **Results Analytics**: EV metrics, win probability, ROI analysis
- **Performance Charts**: Visual simulation result summaries

## API Routes (`app/api/`)

### Optimization Endpoint (`/api/optimize`)
```typescript
POST /api/optimize
{
  slateId: string;
  config: OptimizerConfig;
  seed?: number;
}

Response: {
  runId: string;
  status: "queued" | "running" | "completed" | "failed";
  progress?: number;
}
```

### Run Management (`/api/runs`)
```typescript
GET /api/runs?slateId={slateId}&type={runType}
Response: Array<RunSummary>

GET /api/runs/{runId}  
Response: RunDetails

POST /api/runs/{runId}/export
Response: FileDownload
```

**Features:**
- **Run Discovery**: Find runs by slate, type, date
- **Status Polling**: Real-time run progress updates
- **Artifact Download**: Export results in multiple formats
- **Run Chaining**: Link dependent stages automatically

## State Management

### Global State (Zustand)
```typescript
// Run state management
const useRunStore = create<RunState>((set, get) => ({
  activeRuns: [],
  runHistory: [],
  addRun: (run) => set((state) => ({ 
    activeRuns: [...state.activeRuns, run] 
  })),
  updateRunStatus: (runId, status) => // Update logic
}));

// UI state management  
const useUIStore = create<UIState>((set) => ({
  activeTab: 'optimizer',
  sidebarOpen: true,
  theme: 'system'
}));
```

### Form State (React Hook Form)
- **Validation**: Real-time form validation with Zod schemas
- **Persistence**: Form state persistence across page navigation
- **Auto-save**: Periodic configuration backup

## Component Architecture

### Design System
- **Base**: Shadcn/ui components with Radix UI primitives
- **Styling**: Tailwind CSS with custom design tokens
- **Icons**: Lucide React icon library
- **Animations**: Framer Motion (selective usage)

### Reusable Components
```tsx
// Page layout with consistent structure
<PageContainer 
  title="Stage Name"
  gridMode={mode}
  onGridModeChange={setMode}
>

// Data tables with virtualization
<DataTable 
  data={tableData}
  columns={columnDefs}
  virtualizeRows={true}
/>

// Upload interface with drag/drop
<UploadDropzone 
  accept=".csv"
  onUpload={handleUpload}
  validation={csvSchema}
/>
```

### Performance Optimizations
- **Code Splitting**: Route-based and component-based splitting
- **Virtualization**: Large dataset table virtualization
- **Memoization**: React.memo and useMemo for expensive operations
- **Lazy Loading**: Progressive loading of heavy components

## Integration with Backend

### Process Orchestration
The frontend communicates with the Python backend through:

1. **Direct CLI Calls**: Via Next.js API routes executing Python modules
2. **File System**: Reading/writing parquet and JSON artifacts
3. **Real-time Updates**: Polling for long-running process status
4. **Error Handling**: Comprehensive error boundary implementation

### Data Flow
```
User Input → React Forms → API Routes → Python Processes → Parquet Files → UI Updates
```

### File System Integration
```typescript
// Read pipeline outputs
const lineups = await readParquetFile(
  `data/runs/optimizer/${runId}/lineups.parquet`
);

// Monitor run progress
const manifest = await readJSON(
  `data/runs/optimizer/${runId}/manifest.json`
);
```

## Development

### Local Development
```bash
npm run dev              # Start development server
npm run build           # Production build
npm run test            # Run test suite
npm run test:e2e        # End-to-end tests
```

### Development Server
- **Port**: 3000 (configurable)
- **Hot Reload**: Automatic code reloading
- **Error Overlay**: Development error UI
- **Performance**: React DevTools integration

### Environment Configuration
```bash
# .env.local
NEXT_PUBLIC_API_BASE_URL=http://localhost:3000
PYTHON_ENV_PATH=./.venv/bin/python
DATA_ROOT=./data
```

## Testing

### Unit Tests (Vitest)
- **Location**: `__tests__` directories alongside components
- **Coverage**: Component logic, utilities, API routes
- **Mocking**: MSW for API mocking, file system mocks

### End-to-End Tests (Playwright)  
- **Location**: `e2e/` directory
- **Scenarios**: Full pipeline workflows, error handling
- **Browsers**: Chrome, Firefox, Safari testing

**Example Test:**
```typescript
test('complete optimization workflow', async ({ page }) => {
  await page.goto('/optimizer');
  
  // Upload CSV files
  await uploadProjections(page, 'fixtures/projections.csv');
  
  // Configure optimization
  await setOptimizerConfig(page, { numLineups: 5 });
  
  // Run optimization
  await page.click('[data-testid="run-optimizer"]');
  
  // Verify results
  await expect(page.locator('.lineup-table')).toBeVisible();
});
```

## Dependencies

### Core Framework
```json
{
  "next": "^14.2.10",           // React framework
  "react": "^18.3.1",           // UI library  
  "react-dom": "^18.3.1"       // React DOM renderer
}
```

### UI Components
```json
{
  "@radix-ui/*": "^*",          // Primitive UI components
  "tailwindcss": "^3.4.10",    // Styling framework
  "lucide-react": "^0.452.0",  // Icon library
  "next-themes": "^0.4.6"      // Theme management
}
```

### State & Data
```json
{
  "zustand": "^5.0.8",         // State management
  "@tanstack/react-table": "^8.21.3",  // Data tables
  "zod": "^3.25.76",           // Schema validation
  "papaparse": "^5.5.3"       // CSV parsing
}
```

### Development Tools
```json
{
  "typescript": "5.9.2",       // Type safety
  "vitest": "^3.2.4",         // Unit testing
  "@playwright/test": "^1.55.0"  // E2E testing
}
```

## Deployment

### Production Build
```bash
npm run build              # Create optimized build
npm run start             # Start production server
```

### Static Export (Optional)
```bash
# next.config.mjs
export default {
  output: 'export',
  trailingSlash: true,
  images: { unoptimized: true }
};
```

### Environment Variables
```bash
# Production environment
NODE_ENV=production
NEXT_PUBLIC_API_BASE_URL=https://your-domain.com
```

## Performance Considerations

### Bundle Optimization
- **Tree Shaking**: Unused code elimination
- **Code Splitting**: Route and component level splitting  
- **Image Optimization**: Next.js automatic image optimization
- **Font Optimization**: Automatic font optimization

### Runtime Performance
- **Virtual Scrolling**: Large table performance via `@tanstack/react-virtual`
- **Memoization**: Strategic use of React.memo and useMemo
- **Lazy Loading**: Component lazy loading for initial bundle size

### Monitoring
- **Core Web Vitals**: LCP, FID, CLS tracking
- **Error Tracking**: Comprehensive error boundary implementation
- **Performance Metrics**: Runtime performance monitoring

## Accessibility

### WCAG Compliance
- **Keyboard Navigation**: Full keyboard accessibility
- **Screen Reader**: ARIA labels and semantic HTML
- **Color Contrast**: WCAG AA compliant color schemes
- **Focus Management**: Logical focus order and visible indicators

### Implementation
```tsx
// Semantic HTML structure
<main role="main" aria-label="Optimizer Interface">
  <h1>Lineup Optimizer</h1>
  <section aria-labelledby="config-heading">
    <h2 id="config-heading">Configuration</h2>
    // Form elements with proper labels
  </section>
</main>

// Skip navigation for keyboard users
<a href="#content" className="skip-link">
  Skip to main content
</a>
```

## Future Enhancements

### Planned Features
- **Real-time Collaboration**: Multi-user optimization sessions
- **Advanced Analytics**: Machine learning insights
- **Mobile Optimization**: Responsive design improvements
- **Offline Support**: PWA capabilities for offline usage

### Technical Improvements
- **Server Components**: Migrate to Next.js App Router server components
- **Streaming**: Server-side streaming for large datasets
- **Caching**: Advanced caching strategies for performance
- **WebSockets**: Real-time updates via WebSocket connections