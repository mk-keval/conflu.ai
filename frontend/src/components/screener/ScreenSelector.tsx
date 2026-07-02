import { useScreenStore } from '@/store/screen';
import { SCREEN_TEMPLATES, SCREEN_TEMPLATE_CONFIGS } from '@/lib/constants';

export function ScreenSelector() {
  const { selectedConfig, setConfig } = useScreenStore();

  return (
    <select
      value={selectedConfig}
      onChange={(e) => setConfig(e.target.value)}
      className="rounded border border-dark-400 bg-dark-600 px-3 py-1.5 text-sm text-dark-50 outline-none focus:border-accent"
    >
      {SCREEN_TEMPLATES.map((template) => {
        const config = SCREEN_TEMPLATE_CONFIGS[template];
        return (
          <option key={template} value={template} title={config?.description ?? ''}>
            {template.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
          </option>
        );
      })}
    </select>
  );
}
