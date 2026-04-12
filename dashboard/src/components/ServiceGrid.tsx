import type { Service } from '../api/types';

interface ServiceGridProps {
  services: Record<string, Service> | Service[];
  selectedService?: string | null;
  onServiceSelect?: (service: string) => void;
  selectable?: boolean;
}

export function ServiceGrid({ services, selectedService, onServiceSelect, selectable = false }: ServiceGridProps) {
  const getStatusColor = (status: Service['status']) => {
    switch (status) {
      case 'healthy':
        return 'text-success border-success/30 bg-success/5';
      case 'degraded':
        return 'text-warning border-warning/30 bg-warning/5';
      case 'down':
        return 'text-danger border-danger/30 bg-danger/5';
      case 'unhealthy':
        return 'text-warning border-warning/30 bg-warning/5';
      default:
        return 'text-text-muted border-border bg-bg';
    }
  };

  const getDotColor = (status: Service['status']) => {
    switch (status) {
      case 'healthy': return 'bg-success';
      case 'degraded': return 'bg-warning';
      case 'down': return 'bg-danger';
      case 'unhealthy': return 'bg-warning';
      default: return 'bg-text-muted';
    }
  };

  // Normalize: accept both Record<string, Service> and Service[]
  const normalized: Service[] = Array.isArray(services)
    ? services
    : Object.values(services);

  if (normalized.length === 0) {
    return (
      <div className="flex items-center justify-center py-6">
        <span className="text-xs text-text-muted font-mono">No services</span>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-3 gap-1.5">
      {normalized.map((service) => (
        <button
          key={service.name}
          onClick={() => onServiceSelect?.(service.name)}
          disabled={!selectable}
          className={`
            flex flex-col items-center gap-1 p-2 rounded border transition-colors
            ${selectable ? 'cursor-pointer hover:border-accent/40' : 'cursor-default'}
            ${selectedService === service.name
              ? 'border-accent bg-accent/10 ring-1 ring-accent/50'
              : `border-border bg-bg hover:bg-bg ${getStatusColor(service.status)}`
            }
          `}
        >
          {/* Status dot */}
          <span className={`w-2 h-2 rounded-full ${getDotColor(service.status)} ${service.status === 'down' ? 'critical-pulse' : ''}`} />
          {/* Name */}
          <span className="text-2xs font-mono text-text-primary text-center leading-tight">
            {service.name?.replace('-service', '').replace(/-/g, ' ') ?? service.name}
          </span>
          {/* Status */}
          <span className={`text-2xs font-mono uppercase tracking-wider opacity-75 ${
            service.status === 'healthy' ? 'text-success' :
            service.status === 'degraded' || service.status === 'unhealthy' ? 'text-warning' :
            service.status === 'down' ? 'text-danger' : 'text-text-muted'
          }`}>
            {service.status}
          </span>
        </button>
      ))}
    </div>
  );
}
