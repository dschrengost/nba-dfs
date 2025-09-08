# Components Module (UI Components)

The components module provides a comprehensive library of reusable React components built on Shadcn/ui and Radix UI primitives, specifically designed for the NBA-DFS application interface and data visualization needs.

## Overview

The components module contains:
- **UI Primitives**: Base components using Shadcn/ui design system
- **Domain-Specific Components**: DFS-specific UI elements (lineup displays, player tables)
- **Layout Components**: Page structure, navigation, and layout utilities
- **Data Visualization**: Tables, charts, and metrics displays  
- **Interactive Elements**: Forms, controls, and input components
- **Theme System**: Consistent theming and dark mode support

## Architecture

```
components/
├── ui/                 # Base UI components (Shadcn/ui)
├── lineups/           # Lineup-specific components
├── metrics/           # Analytics and metrics displays
├── runs/              # Run management components
├── theme/             # Theme and styling components
└── aceternity/        # Advanced UI effects and animations
```

## Design System

### Foundation
- **Base**: Shadcn/ui component library
- **Primitives**: Radix UI for accessibility and behavior
- **Styling**: Tailwind CSS with custom design tokens
- **Theme**: Light/dark mode with system preference detection
- **Icons**: Lucide React icon library

### Design Tokens
```css
/* Color palette */
:root {
  --primary: 222.2 84% 4.9%;
  --primary-foreground: 210 40% 98%;
  --secondary: 210 40% 96%;
  --muted: 210 40% 96%;
  --accent: 210 40% 96%;
  --destructive: 0 84.2% 60.2%;
}

/* Typography */
--font-sans: Inter, sans-serif;
--font-mono: 'JetBrains Mono', monospace;

/* Spacing scale */
--spacing-xs: 0.25rem;   /* 4px */
--spacing-sm: 0.5rem;    /* 8px */
--spacing-md: 1rem;      /* 16px */
--spacing-lg: 1.5rem;    /* 24px */
--spacing-xl: 2rem;      /* 32px */
```

## Core UI Components (`components/ui/`)

### Layout Components

#### PageContainer (`PageContainer.tsx`)
```tsx
// Main page layout wrapper
<PageContainer 
  title="Optimizer"
  subtitle="Generate optimal lineups"
  gridMode="loaded"
  onGridModeChange={setGridMode}
>
  {children}
</PageContainer>
```

**Features:**
- Consistent page structure across all views
- Grid mode switching (empty, loading, loaded, error)
- Responsive layout with mobile optimization
- Accessibility-compliant heading hierarchy

#### TopStatusBar (`TopStatusBar.tsx`)
```tsx
// Global status and notifications
<TopStatusBar 
  status="ready"
  activeRuns={runs}
  notifications={messages}
/>
```

**Features:**
- System status indicator
- Active run progress tracking
- Notification center
- Theme toggle integration

#### TopTabs (`TopTabs.tsx`)
```tsx
// Main navigation tabs
<TopTabs 
  activeTab="optimizer"
  onTabChange={setActiveTab}
  tabs={['optimizer', 'variants', 'field', 'simulator']}
/>
```

### Interactive Components

#### ControlsBar (`ControlsBar.tsx`)
**Purpose**: Primary action controls for each application stage

```tsx
<ControlsBar 
  mode="optimizer"
  config={optimizerConfig}
  onConfigChange={setConfig}
  onRun={handleOptimization}
  disabled={isRunning}
/>
```

**Features:**
- Stage-specific control sets
- Configuration form integration
- Real-time validation feedback
- Action button states (idle, loading, success, error)

#### UploadDropzone (`dropzone.tsx`)
```tsx
<UploadDropzone 
  accept=".csv"
  multiple={true}
  onUpload={handleFileUpload}
  validation={csvSchema}
>
  Drop CSV files here or click to browse
</UploadDropzone>
```

**Features:**
- Drag and drop file upload
- File type validation
- Progress indicators
- Error handling and retry logic

### Data Display Components

#### DataTable (`data-table.tsx`)
```tsx
<DataTable 
  data={lineups}
  columns={lineupColumns}
  sorting={true}
  filtering={true}
  pagination={{ pageSize: 50 }}
  virtualization={true}
/>
```

**Features:**
- **Performance**: Virtual scrolling for large datasets
- **Interaction**: Sorting, filtering, column resizing
- **Export**: CSV/JSON export functionality
- **Accessibility**: Full keyboard navigation support

#### MetricsDrawer (`MetricsDrawer.tsx`)
```tsx
<MetricsDrawer 
  open={showMetrics}
  metrics={runMetrics}
  charts={chartConfigs}
/>
```

**Features:**
- Collapsible analytics panel
- Real-time metrics updates
- Interactive charts and visualizations
- Performance comparison tools

### Form Components

#### Configuration Forms
```tsx
// Optimizer configuration
<OptimizerConfigForm 
  config={config}
  onChange={updateConfig}
  validation={configErrors}
/>

// Field sampler settings
<FieldConfigForm 
  config={fieldConfig}
  onSubmit={handleFieldSampling}
/>
```

**Features:**
- Real-time validation with Zod schemas
- Auto-save functionality
- Conditional field rendering
- Help tooltips and documentation links

## Domain-Specific Components

### Lineup Components (`components/lineups/`)

#### LineupViews (`LineupViews.tsx`)
```tsx
<LineupViews 
  lineups={optimizedLineups}
  viewMode="table"
  groupBy="salary"
  showMetrics={true}
/>
```

**Features:**
- **Multiple Views**: Table, card grid, compact list
- **Grouping**: By salary tier, position, team
- **Metrics**: Embedded analytics and comparisons
- **Export**: DraftKings-formatted CSV export

#### LineupTable (`LineupTable.tsx`)
```tsx
<LineupTable 
  lineups={lineups}
  columns={['players', 'salary', 'proj_fp', 'actions']}
  selectable={true}
  onSelectionChange={setSelected}
/>
```

**Features:**
- Lineup-optimized table design
- Player name display with positions
- Salary formatting and validation indicators
- Bulk selection and actions

#### PlayerCell (`PlayerCell.tsx`)
```tsx
<PlayerCell 
  players={lineupPlayers}
  format="compact"
  showPositions={true}
  showSalaries={false}
/>
```

**Features:**
- Condensed player display for lineups
- Position badge indicators
- Team color coding
- Hover tooltips with detailed stats

### Metrics Components (`components/metrics/`)

#### RunSummary (`RunSummary.tsx`)
```tsx
<RunSummary 
  run={runData}
  showDetails={expanded}
  onToggleDetails={setExpanded}
/>
```

**Features:**
- Run metadata display
- Performance metrics visualization
- Execution timeline
- Error reporting and diagnostics

#### IngestSummary (`IngestSummary.tsx`)
```tsx
<IngestSummary 
  summary={ingestStats}
  validationErrors={errors}
  onRetry={handleRetry}
/>
```

**Features:**
- Data ingestion statistics
- Validation error reporting
- Data quality indicators
- Retry and correction workflows

### Run Management (`components/runs/`)

#### RunTracker (`RunTracker.tsx`)
```tsx
<RunTracker 
  activeRuns={runningProcesses}
  onCancel={cancelRun}
  onViewResults={showResults}
/>
```

**Features:**
- Real-time run status tracking
- Progress indicators with ETA
- Cancel and retry actions
- Results navigation

## Theme System (`components/theme/`)

### ThemeProvider (`ThemeProvider.tsx`)
```tsx
<ThemeProvider 
  attribute="class"
  defaultTheme="system"
  enableSystem={true}
  disableTransitionOnChange={false}
>
  {children}
</ThemeProvider>
```

**Features:**
- System preference detection
- Smooth theme transitions
- Theme persistence across sessions
- CSS custom property integration

### Theme Toggle
```tsx
<ThemeToggle 
  size="sm"
  variant="outline"
  showLabel={false}
/>
```

**Features:**
- Light/dark/system mode cycling
- Visual feedback for current theme
- Accessibility-compliant implementation
- Keyboard navigation support

## Advanced Components (`components/aceternity/`)

### AnimatedElements
**Purpose**: Enhanced UI effects for data visualization

```tsx
<AnimatedNumber 
  value={totalEV}
  duration={800}
  formatter={(n) => `$${n.toFixed(2)}`}
/>

<ParticleBackground 
  density={50}
  speed={1.2}
  color="hsl(var(--primary))"
/>
```

**Features:**
- Smooth number animations
- Particle effects for backgrounds
- Loading state animations
- Performance-optimized rendering

## Accessibility Features

### WCAG Compliance
- **Keyboard Navigation**: Full keyboard support for all interactive elements
- **Screen Readers**: Proper ARIA labels and semantic HTML
- **Color Contrast**: WCAG AA compliant color combinations
- **Focus Management**: Visible focus indicators and logical tab order

### Implementation Examples
```tsx
// Accessible data table
<Table role="table" aria-label="Lineup Results">
  <TableHeader>
    <TableRow role="row">
      <TableHead 
        role="columnheader" 
        aria-sort={sortDirection}
      >
        Players
      </TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    {lineups.map((lineup, index) => (
      <TableRow 
        key={lineup.id}
        role="row"
        aria-rowindex={index + 1}
      >
        <TableCell role="cell">
          {/* Player data */}
        </TableCell>
      </TableRow>
    ))}
  </TableBody>
</Table>

// Skip navigation
<a 
  href="#main-content" 
  className="skip-link sr-only focus:not-sr-only"
>
  Skip to main content
</a>
```

### Motion Preferences
```tsx
// Respect user motion preferences
const prefersReducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)');

<motion.div
  animate={{ opacity: 1 }}
  transition={{ 
    duration: prefersReducedMotion ? 0 : 0.3 
  }}
>
  {content}
</motion.div>
```

## Performance Optimizations

### Virtual Scrolling
```tsx
// Handle large datasets efficiently
import { useVirtualizer } from '@tanstack/react-virtual';

function VirtualizedLineupTable({ lineups }) {
  const virtualizer = useVirtualizer({
    count: lineups.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 64,
  });

  return (
    <div ref={parentRef} className="h-400 overflow-auto">
      <div style={{ height: virtualizer.getTotalSize() }}>
        {virtualizer.getVirtualItems().map((item) => (
          <LineupRow 
            key={item.key}
            lineup={lineups[item.index]}
            style={{
              height: item.size,
              transform: `translateY(${item.start}px)`
            }}
          />
        ))}
      </div>
    </div>
  );
}
```

### Memoization
```tsx
// Prevent unnecessary re-renders
const LineupCard = memo(({ lineup, selected, onToggle }) => {
  const handleClick = useCallback(() => {
    onToggle(lineup.id);
  }, [lineup.id, onToggle]);

  const formattedSalary = useMemo(() => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
    }).format(lineup.total_salary);
  }, [lineup.total_salary]);

  return (
    <Card 
      className={cn('cursor-pointer', selected && 'ring-2')}
      onClick={handleClick}
    >
      <CardContent>
        <div className="font-medium">{formattedSalary}</div>
        <PlayerList players={lineup.players} />
      </CardContent>
    </Card>
  );
});
```

## Development Workflow

### Component Development
```bash
# Start Storybook (if configured)
npm run storybook

# Component testing
npm run test components/

# Visual regression testing
npm run test:visual
```

### Style Guidelines
```tsx
// Component structure template
interface ComponentProps {
  // Props with clear types and docs
  data: DataType;
  onAction?: (id: string) => void;
  variant?: 'default' | 'compact';
  className?: string;
}

export function Component({ 
  data, 
  onAction, 
  variant = 'default',
  className 
}: ComponentProps) {
  return (
    <div className={cn('base-styles', className)}>
      {/* Component implementation */}
    </div>
  );
}

// Export with proper display name
Component.displayName = 'Component';
```

## Testing Strategy

### Unit Tests
```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { LineupTable } from './LineupTable';

describe('LineupTable', () => {
  const mockLineups = [
    {
      id: '1',
      players: ['player1', 'player2'],
      total_salary: 49500,
      proj_fp: 285.5
    }
  ];

  it('renders lineup data correctly', () => {
    render(<LineupTable lineups={mockLineups} />);
    
    expect(screen.getByText('$49,500')).toBeInTheDocument();
    expect(screen.getByText('285.5')).toBeInTheDocument();
  });

  it('handles row selection', () => {
    const onSelect = jest.fn();
    render(
      <LineupTable 
        lineups={mockLineups}
        onSelectionChange={onSelect}
      />
    );

    fireEvent.click(screen.getByRole('checkbox'));
    expect(onSelect).toHaveBeenCalledWith(['1']);
  });
});
```

### Visual Tests
```tsx
// Playwright component testing
import { test, expect } from '@playwright/experimental-ct-react';
import { LineupViews } from './LineupViews';

test('lineup views display correctly', async ({ mount }) => {
  const component = await mount(
    <LineupViews 
      lineups={testLineups}
      viewMode="table" 
    />
  );

  await expect(component).toHaveScreenshot('lineup-table-view.png');
});
```

## Future Enhancements

### Planned Features
- **Virtual Tables**: Enhanced performance for massive datasets
- **Advanced Filters**: Complex filtering UI with query builder
- **Collaborative Features**: Real-time collaboration on lineup building
- **Mobile Optimization**: Enhanced mobile responsive design

### Performance Improvements
- **Component Streaming**: React 18 concurrent features
- **Intersection Observer**: Lazy loading for off-screen components
- **Web Workers**: Background processing for heavy computations
- **Service Worker Caching**: Offline component functionality