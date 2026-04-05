import { useEffect, useMemo, useState } from 'react';
import { TopTabs } from './components/layout/TopTabs';
import { Button } from './components/ui/button';
import { CapturePage } from './features/capture/CapturePage';
import { HomePage } from './features/home/HomePage';
import { LivePage } from './features/live/LivePage';
import { QuickPage } from './features/quick/QuickPage';
import { RegisterPage } from './features/register/RegisterPage';
import type { TabKey } from './types/domain';

type ThemeMode = 'light' | 'dark';

export function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('home');
  const [theme, setTheme] = useState<ThemeMode>('light');
  const [toast, setToast] = useState<{ message: string; tone: 'success' | 'error' | 'info' } | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem('mf-theme');
    const next = saved === 'dark' ? 'dark' : 'light';
    setTheme(next);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('mf-theme', theme);
  }, [theme]);

  useEffect(() => {
    function onNavigateTab(e: Event) {
      const custom = e as CustomEvent;
      const tab = custom.detail as TabKey | undefined;
      if (tab && ['home', 'live', 'quick', 'register', 'capture'].includes(tab)) {
        setActiveTab(tab);
      }
    }

    function onToast(e: Event) {
      const custom = e as CustomEvent;
      const payload = custom.detail as { message?: string; tone?: 'success' | 'error' | 'info' } | undefined;
      const message = payload?.message?.trim();
      if (!message) return;
      setToast({ message, tone: payload?.tone ?? 'info' });
    }

    window.addEventListener('mf:navigate-tab', onNavigateTab as EventListener);
    window.addEventListener('mf:toast', onToast as EventListener);
    return () => {
      window.removeEventListener('mf:navigate-tab', onNavigateTab as EventListener);
      window.removeEventListener('mf:toast', onToast as EventListener);
    };
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 2400);
    return () => window.clearTimeout(t);
  }, [toast]);

  const content = useMemo(() => {
    switch (activeTab) {
      case 'live':
        return <LivePage />;
      case 'quick':
        return <QuickPage />;
      case 'register':
        return <RegisterPage />;
      case 'capture':
        return <CapturePage />;
      case 'home':
      default:
        return <HomePage />;
    }
  }, [activeTab]);

  return (
    <div className="app-bg">
      <div className="ipad-frame">
        <header className="top-bar">
          <Button className="icon-circle" variant="ghost" size="icon" aria-label="home" onClick={() => setActiveTab('home')}>⌂</Button>
          <TopTabs activeTab={activeTab} onChange={setActiveTab} />
          <Button
            className="icon-circle"
            variant="ghost"
            size="icon"
            aria-label="theme-toggle"
            onClick={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}
          >
            {theme === 'dark' ? '☀' : '☾'}
          </Button>
        </header>

        <div className="top-meta">
          <h1 className="top-title">MissingFind Console</h1>
          <p className="top-subtitle">Capture · Live · Quick · Register</p>
        </div>

        <main className="content">{content}</main>

        <footer className="app-footer">Ready for real-time item recovery workflows</footer>
      </div>

      {toast && (
        <div className={`toast toast--${toast.tone}`} role="status" aria-live="polite">
          {toast.message}
        </div>
      )}
    </div>
  );
}
