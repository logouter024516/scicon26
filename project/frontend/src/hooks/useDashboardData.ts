import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import type { ClipDto, SummaryDto } from '../types/domain';

export function useDashboardData() {
  const [summary, setSummary] = useState<SummaryDto | null>(null);
  const [clips, setClips] = useState<ClipDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function run(mountedRef?: { value: boolean }) {
    const mounted = mountedRef ? mountedRef.value : true;
    if (!mounted) return;
      setLoading(true);
      setError(null);
      try {
        const [s, c] = await Promise.all([apiClient.summary(), apiClient.recentClips()]);
        if (mountedRef && !mountedRef.value) return;
        setSummary(s);
        setClips(c);
      } catch (e) {
        if (mountedRef && !mountedRef.value) return;
        setError(e instanceof Error ? e.message : 'Unknown error');
      } finally {
        if (!mountedRef || mountedRef.value) setLoading(false);
      }
  }

  useEffect(() => {
    const mountedRef = { value: true };

    run(mountedRef);

    const timer = window.setInterval(() => {
      run(mountedRef);
    }, 5000);

    return () => {
      mountedRef.value = false;
      window.clearInterval(timer);
    };
  }, []);

  return { summary, clips, loading, error, refresh: () => run() };
}
