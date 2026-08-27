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
  { id: 'technical', label: 'Technical', icon: <LineChart className="h-4 w-4" /> },
  { id: 'fundamental', label: 'Fundamental', icon: <BarChart3 className="h-4 w-4" /> },
  { id: 'growth', label: 'Growth', icon: <TrendingUp className="h-4 w-4" /> },
  { id: 'earnings', label: 'Earnings', icon: <DollarSign className="h-4 w-4" /> },
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

function MetricDetail({ metricKey, onBack }: { metricKey: string; onBack: () => void }) {
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
        className="flex items-center gap-1 text-xs text-text-muted hover:text-accent transition-colors mb-4"
      >
        <ArrowLeft className="h-3 w-3" />
        Back to list
      </button>

      {/* Header */}
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-text-primary">{lesson.label}</h3>
        <span className="text-xs text-text-muted font-mono">{metricKey}</span>
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
          <div className="bg-bg-muted/50 rounded-lg p-3 font-mono text-sm text-text-primary border border-border/50">
            {renderValueText(metricKey, 'example') ?? lesson.what?.slice(0, 120) ?? '—'}
          </div>
          <p className="text-xs text-text-muted mt-1 italic">
            Shows how a value would be interpreted — actual wording adapts to each stock's number.
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
              <p className="text-xs text-text-muted mt-1 italic">{enhanced.valueContext}</p>
            )}
            {enhanced.actionable && (
              <p className="text-xs text-accent mt-2 font-medium">{enhanced.actionable}</p>
            )}
            <span className="block text-2xs text-text-muted mt-1">
              Source: {enhanced.source === 'llm' ? 'AI-enhanced' : 'template'}
            </span>
          </Section>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="text-xs font-semibold text-accent uppercase tracking-wider mb-1.5">{title}</h4>
      <div className="text-sm text-text-primary leading-relaxed">{children}</div>
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

export function ConceptExplorer({ initialMetric, onClose, className }: ConceptExplorerProps) {
  const [activeTab, setActiveTab] = useState<Tab>('metrics');
  const [metricTab, setMetricTab] = useState('technical');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedMetric, setSelectedMetric] = useState<string | null>(initialMetric ?? null);
  const [selectedModule, setSelectedModule] = useState<string | null>(null);

  const categories = useMemo(() => getMetricCategories(), []);

  // Filtered metrics for current tab + search
  const filteredMetrics = useMemo(() => {
    const keys = categories[metricTab as keyof typeof categories] ?? [];
    if (!searchQuery) return keys;
    const results = searchMetrics(searchQuery);
    return results
      .filter((r) => r.category === metricTab)
      .map((r) => r.key);
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
    <div className={cn('flex flex-col h-full', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-accent" />
          <h2 className="text-sm font-semibold text-text-primary">Concept Explorer</h2>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-xs text-text-muted hover:text-text-primary transition-colors"
          >
            Close
          </button>
        )}
      </div>

      {/* Search */}
      <div className="px-4 py-2 border-b border-border">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-text-muted" />
          <input
            type="text"
            placeholder="Search concepts, metrics, terms..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-sm bg-bg-muted border border-border rounded-md
                       text-text-primary placeholder-text-muted
                       focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent"
          />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border px-2">
        <TabButton active={activeTab === 'metrics'} onClick={() => setActiveTab('metrics')}>
          <BarChart3 className="h-3.5 w-3.5" />
          Metrics
        </TabButton>
        <TabButton active={activeTab === 'modules'} onClick={() => setActiveTab('modules')}>
          <BookOpen className="h-3.5 w-3.5" />
          Modules
        </TabButton>
        <TabButton active={activeTab === 'glossary'} onClick={() => setActiveTab('glossary')}>
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
              <div className="flex gap-1 px-3 py-2 border-b border-border/50 overflow-x-auto">
                {METRIC_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => { setMetricTab(tab.id); setSelectedMetric(null); }}
                    className={cn(
                      'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium whitespace-nowrap transition-colors',
                      metricTab === tab.id
                        ? 'bg-accent/15 text-accent'
                        : 'text-text-muted hover:text-text-primary hover:bg-bg-muted'
                    )}
                  >
                    {tab.icon}
                    {tab.label}
                  </button>
                ))}
              </div>
            )}

            <div className="p-3 space-y-1">
              {filteredMetrics.length === 0 ? (
                <div className="text-center text-text-muted text-sm py-8">
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
                      className="w-full flex items-center justify-between px-3 py-2 rounded-lg
                                 hover:bg-bg-muted transition-colors text-left group"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="shrink-0 text-text-muted">
                          {CATEGORY_ICONS[metricTab] ?? <BarChart3 className="h-3 w-3" />}
                        </span>
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-text-primary truncate">
                            {lesson.label}
                          </div>
                          <div className="text-xs text-text-muted truncate">
                            {lesson.what?.slice(0, 80)}...
                          </div>
                        </div>
                      </div>
                      <ChevronRight className="h-4 w-4 text-text-muted shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </button>
                  );
                })
              )}
            </div>
          </>
        )}

        {activeTab === 'modules' && (
          <div className="p-3 space-y-2">
            {selectedModule ? (
              <ModuleDetail moduleKey={selectedModule} onBack={() => setSelectedModule(null)} />
            ) : (
              Object.entries(modules).map(([key, module]) => (
                <button
                  key={key}
                  onClick={() => setSelectedModule(key)}
                  className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg
                             hover:bg-bg-muted transition-colors text-left group"
                >
                  <div>
                    <div className="text-sm font-medium text-text-primary">{module.title}</div>
                    <div className="text-xs text-text-muted mt-0.5 line-clamp-2">{module.whatItIs}</div>
                  </div>
                  <ChevronRight className="h-4 w-4 text-text-muted shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                </button>
              ))
            )}
          </div>
        )}

        {activeTab === 'glossary' && (
          <div className="p-3 space-y-0.5">
            {glossaryEntries.map((entry: { term: string; definition: string }) => (
              <div
                key={entry.term}
                className="px-3 py-2 rounded-lg hover:bg-bg-muted transition-colors"
              >
                <div className="text-sm font-medium text-text-primary">{entry.term}</div>
                <div className="text-xs text-text-muted mt-0.5">{entry.definition}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ──

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors border-b-2 -mb-[1px]',
        active
          ? 'border-accent text-accent'
          : 'border-transparent text-text-muted hover:text-text-primary'
      )}
    >
      {children}
    </button>
  );
}

function ModuleDetail({ moduleKey, onBack }: { moduleKey: string; onBack: () => void }) {
  const modules = getAllModuleLessons();
  const module = modules[moduleKey];

  if (!module) {
    return (
      <div className="text-center text-text-muted text-sm py-8">
        Module &ldquo;{moduleKey}&rdquo; not found.
      </div>
    );
  }

  return (
    <div className="animate-in fade-in slide-in-from-right-2 duration-200">
      <button
        onClick={onBack}
        className="flex items-center gap-1 text-xs text-text-muted hover:text-accent transition-colors mb-3"
      >
        <ArrowLeft className="h-3 w-3" />
        Back to modules
      </button>

      <div className="p-3 rounded-lg border border-border bg-bg-muted/30">
        <h3 className="text-base font-semibold text-text-primary mb-1">{module.title}</h3>
        <p className="text-sm text-text-muted">{module.whatItIs}</p>
        {module.whatItIs.length > 120 && (
          <p className="text-xs text-text-muted mt-2 italic">
            {module.whyItMatters}
          </p>
        )}
      </div>
    </div>
  );
}
