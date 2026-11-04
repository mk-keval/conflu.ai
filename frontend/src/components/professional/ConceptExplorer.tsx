import { useState, useMemo } from 'react';
import {
  BookOpen,
  Search,
  TrendingUp,
  BarChart3,
  DollarSign,
  Brain,
  LineChart,
  Globe,
  ChevronRight,
  ArrowLeft,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import { renderValueText } from '@/content/index';
import {
  searchMetrics,
  getMetricLesson,
  getMetricCategories,
  getAllModuleLessons,
  getGlossary,
  searchGlossary,
  useMetricExplanation,
} from '@/hooks/useEducation';

// ── Tab Definitions ──

type Tab = 'metrics' | 'modules' | 'glossary';

interface MetricTab {
  id: string;
  label: string;
  icon: React.ReactNode;
}

const METRIC_TABS: MetricTab[] = [
  {
    id: 'technical',
    label: 'Technical',
    icon: <LineChart className="h-4 w-4" />,
  },
  {
    id: 'fundamental',
    label: 'Fundamental',
    icon: <BarChart3 className="h-4 w-4" />,
  },
  { id: 'growth', label: 'Growth', icon: <TrendingUp className="h-4 w-4" /> },
  {
    id: 'earnings',
    label: 'Earnings',
    icon: <DollarSign className="h-4 w-4" />,
  },
  { id: 'sentiment', label: 'Sentiment', icon: <Brain className="h-4 w-4" /> },
];

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  technical: <LineChart className="h-3 w-3" />,
  fundamental: <BarChart3 className="h-3 w-3" />,
  growth: <TrendingUp className="h-3 w-3" />,
  earnings: <DollarSign className="h-3 w-3" />,
  sentiment: <Brain className="h-3 w-3" />,
};

// ── Helpers ──

// ── Components ──

function MetricDetail({
  metricKey,
  onBack,
}: {
  metricKey: string;
  onBack: () => void;
}) {
  const lesson = getMetricLesson(metricKey);
  const { data: enhanced } = useMetricExplanation(metricKey);

  if (!lesson) {
    return (
      <div className="p-6 text-center text-text-muted">
        No lesson found for &ldquo;{metricKey}&rdquo;
      </div>
    );
  }

  return (
    <div className="animate-in fade-in slide-in-from-right-2 duration-200">
      {/* Back */}
      <button
        onClick={onBack}
        className="mb-4 flex items-center gap-1 text-xs text-text-muted transition-colors hover:text-accent"
      >
        <ArrowLeft className="h-3 w-3" />
        Back to list
      </button>

      {/* Header */}
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-text-primary">
          {lesson.label}
        </h3>
        <span className="font-mono text-xs text-text-muted">{metricKey}</span>
      </div>

      {/* Lesson content */}
      <div className="space-y-4">
        <Section title="What is it?">
          <p>{lesson.what}</p>
        </Section>

        <Section title="Why it matters">
          <p>{lesson.whyMatters}</p>
        </Section>

        <Section title="How to read the value">
          <div className="bg-bg-muted/50 rounded-lg border border-border/50 p-3 font-mono text-sm text-text-primary">
            {renderValueText(metricKey, 'example') ??
              lesson.what?.slice(0, 120) ??
              '—'}
          </div>
          <p className="mt-1 text-xs italic text-text-muted">
            Shows how a value would be interpreted — actual wording adapts to
            each stock's number.
          </p>
        </Section>

        <Section title="Scoring impact">
          <p className="text-sm">{lesson.scoringImpact}</p>
        </Section>

        {/* Enhanced explanation from backend */}
        {enhanced && (
          <Section title="AI Analysis">
            <p className="text-sm">{enhanced.plainEnglish}</p>
            {enhanced.valueContext && (
              <p className="mt-1 text-xs italic text-text-muted">
                {enhanced.valueContext}
              </p>
            )}
            {enhanced.actionable && (
              <p className="mt-2 text-xs font-medium text-accent">
                {enhanced.actionable}
              </p>
            )}
            <span className="text-2xs mt-1 block text-text-muted">
              Source: {enhanced.source === 'llm' ? 'AI-enhanced' : 'template'}
            </span>
          </Section>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-accent">
        {title}
      </h4>
      <div className="text-sm leading-relaxed text-text-primary">
        {children}
      </div>
    </div>
  );
}

// ── Main Component ──

interface ConceptExplorerProps {
  /** Initial metric to show (for deep-linking from verdict cards) */
  initialMetric?: string;
  /** Called when the component is dismissed */
  onClose?: () => void;
  className?: string;
}

export function ConceptExplorer({
  initialMetric,
  onClose,
  className,
}: ConceptExplorerProps) {
  const [activeTab, setActiveTab] = useState<Tab>('metrics');
  const [metricTab, setMetricTab] = useState('technical');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedMetric, setSelectedMetric] = useState<string | null>(
    initialMetric ?? null
  );
  const [selectedModule, setSelectedModule] = useState<string | null>(null);

  const categories = useMemo(() => getMetricCategories(), []);

  // Filtered metrics for current tab + search
  const filteredMetrics = useMemo(() => {
    const keys = categories[metricTab as keyof typeof categories] ?? [];
    if (!searchQuery) return keys;
    const results = searchMetrics(searchQuery);
    return results.filter((r) => r.category === metricTab).map((r) => r.key);
  }, [categories, metricTab, searchQuery]);

  // Module lessons
  const modules = useMemo(() => getAllModuleLessons(), []);

  // Glossary entries
  const glossaryEntries = useMemo(() => {
    if (!searchQuery) return getGlossary();
    return searchGlossary(searchQuery);
  }, [searchQuery]);

  // If a specific metric is selected, show its detail view
  if (selectedMetric) {
    return (
      <div className={cn('p-4', className)}>
        <MetricDetail
          metricKey={selectedMetric}
          onBack={() => setSelectedMetric(null)}
        />
      </div>
    );
  }

  return (
    <div className={cn('flex h-full flex-col', className)}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-accent" />
          <h2 className="text-sm font-semibold text-text-primary">
            Concept Explorer
          </h2>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-xs text-text-muted transition-colors hover:text-text-primary"
          >
            Close
          </button>
        )}
      </div>

      {/* Search */}
      <div className="border-b border-border px-4 py-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
          <input
            type="text"
            placeholder="Search concepts, metrics, terms..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-bg-muted w-full rounded-md border border-border py-1.5 pl-8 pr-3 text-sm text-text-primary placeholder-text-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border px-2">
        <TabButton
          active={activeTab === 'metrics'}
          onClick={() => setActiveTab('metrics')}
        >
          <BarChart3 className="h-3.5 w-3.5" />
          Metrics
        </TabButton>
        <TabButton
          active={activeTab === 'modules'}
          onClick={() => setActiveTab('modules')}
        >
          <BookOpen className="h-3.5 w-3.5" />
          Modules
        </TabButton>
        <TabButton
          active={activeTab === 'glossary'}
          onClick={() => setActiveTab('glossary')}
        >
          <Globe className="h-3.5 w-3.5" />
          Glossary
        </TabButton>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'metrics' && (
          <>
            {/* Sub-tabs */}
            {!searchQuery && (
              <div className="flex gap-1 overflow-x-auto border-b border-border/50 px-3 py-2">
                {METRIC_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => {
                      setMetricTab(tab.id);
                      setSelectedMetric(null);
                    }}
                    className={cn(
                      'flex items-center gap-1.5 whitespace-nowrap rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                      metricTab === tab.id
                        ? 'bg-accent/15 text-accent'
                        : 'hover:bg-bg-muted text-text-muted hover:text-text-primary'
                    )}
                  >
                    {tab.icon}
                    {tab.label}
                  </button>
                ))}
              </div>
            )}

            <div className="space-y-1 p-3">
              {filteredMetrics.length === 0 ? (
                <div className="py-8 text-center text-sm text-text-muted">
                  No metrics match &ldquo;{searchQuery}&rdquo;
                </div>
              ) : (
                filteredMetrics.map((key) => {
                  const lesson = getMetricLesson(key);
                  if (!lesson) return null;
                  return (
                    <button
                      key={key}
                      onClick={() => setSelectedMetric(key)}
                      className="hover:bg-bg-muted group flex w-full items-center justify-between rounded-lg px-3 py-2 text-left transition-colors"
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        <span className="shrink-0 text-text-muted">
                          {CATEGORY_ICONS[metricTab] ?? (
                            <BarChart3 className="h-3 w-3" />
                          )}
                        </span>
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-text-primary">
                            {lesson.label}
                          </div>
                          <div className="truncate text-xs text-text-muted">
                            {lesson.what?.slice(0, 80)}...
                          </div>
                        </div>
                      </div>
                      <ChevronRight className="h-4 w-4 shrink-0 text-text-muted opacity-0 transition-opacity group-hover:opacity-100" />
                    </button>
                  );
                })
              )}
            </div>
          </>
        )}

        {activeTab === 'modules' && (
          <div className="space-y-2 p-3">
            {selectedModule ? (
              <ModuleDetail
                moduleKey={selectedModule}
                onBack={() => setSelectedModule(null)}
              />
            ) : (
              Object.entries(modules).map(([key, module]) => (
                <button
                  key={key}
                  onClick={() => setSelectedModule(key)}
                  className="hover:bg-bg-muted group flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left transition-colors"
                >
                  <div>
                    <div className="text-sm font-medium text-text-primary">
                      {module.title}
                    </div>
                    <div className="mt-0.5 line-clamp-2 text-xs text-text-muted">
                      {module.whatItIs}
                    </div>
                  </div>
                  <ChevronRight className="h-4 w-4 shrink-0 text-text-muted opacity-0 transition-opacity group-hover:opacity-100" />
                </button>
              ))
            )}
          </div>
        )}

        {activeTab === 'glossary' && (
          <div className="space-y-0.5 p-3">
            {glossaryEntries.map(
              (entry: { term: string; definition: string }) => (
                <div
                  key={entry.term}
                  className="hover:bg-bg-muted rounded-lg px-3 py-2 transition-colors"
                >
                  <div className="text-sm font-medium text-text-primary">
                    {entry.term}
                  </div>
                  <div className="mt-0.5 text-xs text-text-muted">
                    {entry.definition}
                  </div>
                </div>
              )
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ──

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        '-mb-[1px] flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-medium transition-colors',
        active
          ? 'border-accent text-accent'
          : 'border-transparent text-text-muted hover:text-text-primary'
      )}
    >
      {children}
    </button>
  );
}

function ModuleDetail({
  moduleKey,
  onBack,
}: {
  moduleKey: string;
  onBack: () => void;
}) {
  const modules = getAllModuleLessons();
  const module = modules[moduleKey];

  if (!module) {
    return (
      <div className="py-8 text-center text-sm text-text-muted">
        Module &ldquo;{moduleKey}&rdquo; not found.
      </div>
    );
  }

  return (
    <div className="animate-in fade-in slide-in-from-right-2 duration-200">
      <button
        onClick={onBack}
        className="mb-3 flex items-center gap-1 text-xs text-text-muted transition-colors hover:text-accent"
      >
        <ArrowLeft className="h-3 w-3" />
        Back to modules
      </button>

      <div className="bg-bg-muted/30 rounded-lg border border-border p-3">
        <h3 className="mb-1 text-base font-semibold text-text-primary">
          {module.title}
        </h3>
        <p className="text-sm text-text-muted">{module.whatItIs}</p>
        {module.whatItIs.length > 120 && (
          <p className="mt-2 text-xs italic text-text-muted">
            {module.whyItMatters}
          </p>
        )}
      </div>
    </div>
  );
}
