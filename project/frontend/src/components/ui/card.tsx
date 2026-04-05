import type { HTMLAttributes, PropsWithChildren } from 'react';
import { cn } from '../../lib/utils';

export function Card({ className, children, ...props }: PropsWithChildren<HTMLAttributes<HTMLElement>>) {
  return (
    <article className={cn('ui-card', className)} {...props}>
      {children}
    </article>
  );
}

export function CardHeader({ className, children, ...props }: PropsWithChildren<HTMLAttributes<HTMLDivElement>>) {
  return (
    <div className={cn('ui-card-header', className)} {...props}>
      {children}
    </div>
  );
}

export function CardTitle({ className, children, ...props }: PropsWithChildren<HTMLAttributes<HTMLHeadingElement>>) {
  return (
    <h3 className={cn('ui-card-title', className)} {...props}>
      {children}
    </h3>
  );
}

export function CardContent({ className, children, ...props }: PropsWithChildren<HTMLAttributes<HTMLDivElement>>) {
  return (
    <div className={cn('ui-card-content', className)} {...props}>
      {children}
    </div>
  );
}
