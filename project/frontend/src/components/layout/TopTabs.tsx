import type { TabKey } from '../../types/domain';
import { Tabs, TabsList, TabsTrigger } from '../ui/tabs';

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: 'home', label: 'Home' },
  { key: 'live', label: 'Live Search' },
  { key: 'quick', label: 'Quick Search' },
  { key: 'register', label: 'Register' },
  { key: 'capture', label: 'Capture' },
];

interface Props {
  activeTab: TabKey;
  onChange: (tab: TabKey) => void;
}

export function TopTabs({ activeTab, onChange }: Props) {
  return (
    <Tabs value={activeTab} onValueChange={(v) => onChange(v as TabKey)}>
      <TabsList className="glass-tabs" aria-label="primary-tabs">
        {tabs.map((t) => (
          <TabsTrigger key={t.key} value={t.key}>
            {t.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}
