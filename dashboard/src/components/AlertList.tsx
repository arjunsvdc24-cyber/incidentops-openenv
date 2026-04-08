import { format } from 'date-fns';
import type { Alert } from '../api/types';

interface AlertListProps {
  alerts: Alert[];
  maxDisplay?: number;
}

export function AlertList({ alerts, maxDisplay = 5 }: AlertListProps) {
  const getSeverityColor = (severity: Alert['severity']) => {
    switch (severity) {
      case 'critical':
        return 'border-l-danger bg-danger/5';
      case 'error':
        return 'border-l-danger bg-danger/5';
      case 'high':
        return 'border-l-orange-500 bg-orange-500/5';
      case 'medium':
        return 'border-l-warning bg-warning/5';
      case 'warning':
        return 'border-l-warning bg-warning/5';
      case 'low':
        return 'border-l-blue-500 bg-blue-500/5';
      case 'info':
      default:
        return 'border-l-border bg-surface';
    }
  };

  const getSeverityBadge = (severity: Alert['severity']) => {
    const colors: Record<Alert['severity'], string> = {
      critical: 'bg-danger text-white',
      high: 'bg-orange-500 text-white',
      medium: 'bg-warning text-black',
      low: 'bg-blue-500 text-white',
      warning: 'bg-warning text-black',
      error: 'bg-danger text-white',
      info: 'bg-text-muted text-text-primary',
    };
    return (
      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${colors[severity] ?? ''}`}>
        {severity}
      </span>
    );
  };

  if (alerts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-text-secondary">
        <svg className="w-12 h-12 mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span className="text-sm">No active alerts</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {alerts.slice(0, maxDisplay).map((alert) => (
        <div
          key={alert.id}
          className={`border-l-4 p-3 rounded-r ${getSeverityColor(alert.severity)}`}
        >
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className="text-sm font-medium text-text-primary truncate">{alert.service}</span>
            {getSeverityBadge(alert.severity)}
          </div>
          <p className="text-xs text-text-secondary line-clamp-2">{alert.message}</p>
          <span className="text-[10px] text-text-secondary/60 mt-1 block">
            {alert.timestamp ? (() => { try { return format(new Date(alert.timestamp), 'HH:mm:ss'); } catch { return '--:--:--'; } })() : '--:--:--'}
          </span>
        </div>
      ))}
      {alerts.length > maxDisplay && (
        <span className="text-xs text-text-secondary text-center py-2">
          +{alerts.length - maxDisplay} more alerts
        </span>
      )}
    </div>
  );
}
