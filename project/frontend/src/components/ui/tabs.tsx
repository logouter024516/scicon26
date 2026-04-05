import { createContext, useContext } from 'react';
import type { ButtonHTMLAttributes, PropsWithChildren } from 'react';
import { cn } from '../../lib/utils';
import { Button } from './button';

interface TabsContextValue {
  value: string;
  onValueChange: (value: string) => void;
}

const TabsContext = createContext<TabsContextValue | null>(null);

interface TabsProps {
  value: string;
  onValueChange: (value: string) => void;
}

export function Tabs({ value, onValueChange, children }: PropsWithChildren<TabsProps>) {
  return <TabsContext.Provider value={{ value, onValueChange }}>{children}</TabsContext.Provider>;
}

export function TabsList({ className, children }: PropsWithChildren<{ className?: string }>) {
  return <div className={cn('ui-tabs-list', className)}>{children}</div>;
}

interface TabsTriggerProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
}

export function TabsTrigger({ value, className, children, ...props }: PropsWithChildren<TabsTriggerProps>) {
  const ctx = useContext(TabsContext);
  if (!ctx) return null;
  const active = ctx.value === value;

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className={cn('ui-tabs-trigger', active && 'active', className)}
      onClick={() => ctx.onValueChange(value)}
      {...props}
    >
      {children}
    </Button>
  );
}
