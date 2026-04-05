import type { ButtonHTMLAttributes, PropsWithChildren } from 'react';
import { cn } from '../../lib/utils';

type Variant = 'default' | 'outline' | 'ghost';
type Size = 'default' | 'icon' | 'sm';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export function Button({
  className,
  variant = 'default',
  size = 'default',
  children,
  ...props
}: PropsWithChildren<ButtonProps>) {
  return (
    <button
      className={cn('ui-btn', `ui-btn--${variant}`, `ui-btn--${size}`, className)}
      {...props}
    >
      {children}
    </button>
  );
}
