import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';

interface Props {
  title: string;
  value: string;
  badgeLabel?: string;
  badgeTone?: 'high' | 'medium' | 'low';
}

export function SummaryCard({ title, value, badgeLabel, badgeTone = 'low' }: Props) {
  return (
    <Card className="summary-card">
      <CardHeader>
        <div className="summary-head">
          <CardTitle>{title}</CardTitle>
          {badgeLabel && <span className={`score-badge score-badge--${badgeTone}`}>{badgeLabel}</span>}
        </div>
      </CardHeader>
      <CardContent>
        <p>{value}</p>
      </CardContent>
      <div className="corner-mark" aria-hidden />
    </Card>
  );
}
