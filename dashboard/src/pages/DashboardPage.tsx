import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getState, getStats } from '../api/client';
import type { Service, Alert, BusinessImpact, SlaDeadline } from '../api/types';
import { format } from 'date-fns';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts';

// ─── Sparkline ───────────────────────────────────────────────────────────────

function Sparkline({ data, color }: { data: number[]; color: string }) {
  if (data.length < 2) return <div className="w-16 h-6" />;
  const points = data.map((v, i) => ({ i, v }));
  return (
    <ResponsiveContainer width={64} height={24}>
      <LineChart data={points}>
        <XAxis dataKey="i" hide />
        <YAxis hide domain={['auto', 'auto']} />
        <Tooltip contentStyle={{ display: 'none' }} />
        <Line
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ─── Animated counter that ticks up ──────────────────────────────────────────

function AnimatedCounter({ value, prefix = '', suffix = '', decimals = 0 }: {
  value: number; prefix?: string; suffix?: string; decimals?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const prevRef = useRef<number>(value);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const prev = prevRef.current;
    if (prev === value) return;
    el.classList.remove('tick-up');
    void el.offsetWidth; // reflow
    el.classList.add('tick-up');
    prevRef.current = value;
  }, [value]);

  return (
    <span ref={ref} className="tabular-nums">
      {prefix}{value.toFixed(decimals)}{suffix}
    </span>
  );
}

// ─── Service Row ─────────────────────────────────────────────────────────────

function ServiceRow({ service, onClick }: {
  service: Service;
  onClick: (name: string) => void;
}) {
  const statusColor: Record<string, string> = {
    healthy: 'text-success',
    degraded: 'text-warning',
    down: 'text-danger',
    unhealthy: 'text-warning',
    unknown: 'text-text-muted',
  };
  const dotColor: Record<string, string> = {
    healthy: 'bg-success',
    degraded: 'bg-warning',
    down: 'bg-danger',
    unhealthy: 'bg-warning',
    unknown: 'bg-text-muted',
  };
  const c = statusColor[service.status] ?? statusColor.unknown;
  const dot = dotColor[service.status] ?? dotColor.unknown;

  const latency = service.latency_ms;
  const errRate = service.error_rate;

  return (
    <button
      onClick={() => onClick(service.name)}
      className="w-full flex items-center gap-2 px-3 py-2 hover:bg-bg rounded transition-colors text-left"
    >
      {/* Status dot */}
      <span className={`w-2 h-2 rounded-full shrink-0 ${dot} ${service.status === 'down' ? 'critical-pulse' : ''}`} />

      {/* Name */}
      <span className="text-xs font-mono text-text-primary flex-1 truncate">{service.name}</span>

      {/* Status pill */}
      <span className={`text-2xs font-mono uppercase tracking-wider ${c}`}>
        {service.status}
      </span>

      {/* Latency */}
      {latency != null && (
        <span className="text-2xs font-mono text-text-muted tabular-nums w-12 text-right">
          {latency > 999 ? `${(latency / 1000).toFixed(1)}s` : `${latency}ms`}
        </span>
      )}

      {/* Error rate */}
      {errRate != null && (
        <span className={`text-2xs font-mono tabular-nums w-10 text-right ${
          errRate > 0.05 ? 'text-danger' : errRate > 0 ? 'text-warning' : 'text-text-muted'
        }`}>
          {(errRate * 100).toFixed(1)}%
        </span>
      )}
    </button>
  );
}

// ─── Service Detail Panel ────────────────────────────────────────────────────

function ServiceDetail({ name, service, history, onClose }: {
  name: string;
  service: Service;
  history: Record<string, number[]>;
  onClose: () => void;
}) {
  const latencyHistory = history[`${name}_latency`] ?? [];
  const errorHistory = history[`${name}_error`] ?? [];
  const cpuHistory = history[`${name}_cpu`] ?? [];

  return (
    <div className="border-t border-border p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-mono font-bold text-text-primary">{name}</span>
        <button onClick={onClose} className="text-text-muted hover:text-text-secondary text-2xs font-mono">
          [close]
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        {service.latency_ms != null && (
          <div className="panel p-2">
            <div className="text-2xs text-text-muted uppercase tracking-wider mb-0.5">Latency</div>
            <div className="text-sm font-mono text-text-primary tabular-nums">
              {service.latency_ms > 999
                ? `${(service.latency_ms / 1000).toFixed(2)}s`
                : `${service.latency_ms.toFixed(0)}ms`}
            </div>
          </div>
        )}
        {service.error_rate != null && (
          <div className="panel p-2">
            <div className="text-2xs text-text-muted uppercase tracking-wider mb-0.5">Error Rate</div>
            <div className={`text-sm font-mono tabular-nums ${(service.error_rate * 100) > 5 ? 'text-danger' : 'text-text-primary'}`}>
              {(service.error_rate * 100).toFixed(2)}%
            </div>
          </div>
        )}
        {service.cpu_percent != null && (
          <div className="panel p-2">
            <div className="text-2xs text-text-muted uppercase tracking-wider mb-0.5">CPU</div>
            <div className="text-sm font-mono text-text-primary tabular-nums">
              {service.cpu_percent.toFixed(1)}%
            </div>
          </div>
        )}
        {service.memory_percent != null && (
          <div className="panel p-2">
            <div className="text-2xs text-text-muted uppercase tracking-wider mb-0.5">Memory</div>
            <div className="text-sm font-mono text-text-primary tabular-nums">
              {service.memory_percent.toFixed(1)}%
            </div>
          </div>
        )}
        {service.requests_per_sec != null && (
          <div className="panel p-2">
            <div className="text-2xs text-text-muted uppercase tracking-wider mb-0.5">Req/s</div>
            <div className="text-sm font-mono text-text-primary tabular-nums">
              {service.requests_per_sec.toFixed(1)}
            </div>
          </div>
        )}
      </div>

      {/* Sparklines */}
      {latencyHistory.length > 1 && (
        <div className="mb-2">
          <div className="text-2xs text-text-muted uppercase tracking-wider mb-1">Latency trend</div>
          <Sparkline data={latencyHistory} color="#58a6ff" />
        </div>
      )}
      {errorHistory.length > 1 && (
        <div className="mb-2">
          <div className="text-2xs text-text-muted uppercase tracking-wider mb-1">Error rate trend</div>
          <Sparkline data={errorHistory.map(v => v * 100)} color="#f85149" />
        </div>
      )}
      {cpuHistory.length > 1 && (
        <div>
          <div className="text-2xs text-text-muted uppercase tracking-wider mb-1">CPU trend</div>
          <Sparkline data={cpuHistory} color="#3fb950" />
        </div>
      )}
    </div>
  );
}

// ─── SLA Countdown ─────────────────────────────────────────────────────────

function SlaCountdown({ deadline }: { deadline: SlaDeadline | null }) {
  if (!deadline) return <span className="text-xs font-mono text-text-muted">--:--</span>;

  const urgencyColor: Record<string, string> = {
    normal: 'text-success',
    elevated: 'text-warning',
    critical: 'text-danger critical-pulse',
  };

  const mm = Math.floor(deadline.minutes_remaining);
  const ss = Math.round((deadline.minutes_remaining - mm) * 60);
  const label = mm > 0 ? `${mm}m ${ss.toString().padStart(2, '0')}s` : `${ss}s`;

  return (
    <span className={`text-xs font-mono tabular-nums ${urgencyColor[deadline.urgency] ?? 'text-text-primary'}`}>
      {label}
    </span>
  );
}

// ─── Alert Row ──────────────────────────────────────────────────────────────

function AlertRow({ alert }: { alert: Alert }) {
  const severityDot: Record<string, string> = {
    critical: 'bg-danger', high: 'bg-orange-500', medium: 'bg-warning',
    low: 'bg-accent', warning: 'bg-warning', error: 'bg-danger',
    info: 'bg-text-muted',
  };
  const dot = severityDot[alert.severity] ?? severityDot.info;
  const isCritical = alert.severity === 'critical';

  return (
    <div className={`flex items-start gap-2 px-3 py-1.5 hover:bg-bg rounded ${isCritical ? 'critical-pulse' : ''}`}>
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 mt-1 ${dot}`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-2xs font-mono text-text-secondary">{alert.service}</span>
          <span className="text-2xs text-text-muted font-mono">
            {format(new Date(alert.timestamp), 'HH:mm:ss')}
          </span>
        </div>
        <p className="text-2xs text-text-primary mt-0.5 line-clamp-2">{alert.message}</p>
      </div>
    </div>
  );
}

// ─── Action Row (slide-in) ───────────────────────────────────────────────────

function ActionRow({ action, index }: {
  action: { step: number; action_type: string; target_service: string; reward: number; cumulative_reward: number };
  index: number;
}) {
  const isPositive = action.reward >= 0;
  return (
    <div
      className="slide-in-down flex items-center gap-2 px-3 py-1.5 hover:bg-bg rounded"
      style={{ animationDelay: `${index * 20}ms` }}
    >
      <span className="text-2xs font-mono text-text-muted w-5 shrink-0">#{action.step}</span>
      <span className="text-2xs font-mono text-text-primary flex-1 truncate">
        {action.action_type?.replace(/_/g, ' ') ?? action.action_type}
        {action.target_service && (
          <span className="text-accent ml-1">→ {action.target_service}</span>
        )}
      </span>
      <span className={`text-2xs font-mono tabular-nums ${isPositive ? 'text-success' : 'text-danger'}`}>
        {isPositive ? '+' : ''}{action.reward.toFixed(2)}
      </span>
      <span className="text-2xs font-mono text-text-muted tabular-nums w-12 text-right">
        Σ {action.cumulative_reward.toFixed(1)}
      </span>
    </div>
  );
}

// ─── Reward Chart ───────────────────────────────────────────────────────────

function RewardChart({ actions }: { actions: Array<{ reward: number; cumulative_reward: number }> }) {
  if (actions.length < 2) return null;
  const data = actions.map((a, i) => ({ i, reward: a.reward, cumulative: a.cumulative_reward }));
  return (
    <div className="h-20">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <XAxis dataKey="i" hide />
          <YAxis hide domain={['auto', 'auto']} />
          <Tooltip
            contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 4, fontSize: 10, fontFamily: 'monospace' }}
            labelStyle={{ display: 'none' }}
            formatter={(v: number, name: string) => [v.toFixed(2), name === 'cumulative' ? 'Σ reward' : 'step reward']}
          />
          <Line type="monotone" dataKey="cumulative" stroke="#58a6ff" strokeWidth={1.5} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Revenue Counter ─────────────────────────────────────────────────────────

function RevenueCounter({ impact }: { impact: BusinessImpact | null }) {
  if (!impact) return <span className="text-xs font-mono text-text-muted">$0.00</span>;
  return (
    <span className="text-xs font-mono tabular-nums text-danger">
      $<AnimatedCounter value={impact.cumulative_revenue_loss_usd} decimals={2} />
    </span>
  );
}

// ─── Status Badge ────────────────────────────────────────────────────────────

function StatusBadge({ initialized, done }: { initialized: boolean; done: boolean }) {
  if (!initialized) {
    return <span className="text-2xs font-mono text-text-muted border border-border px-2 py-0.5 rounded">IDLE</span>;
  }
  if (done) {
    return <span className="text-2xs font-mono text-success border border-success/30 px-2 py-0.5 rounded">DONE</span>;
  }
  return <span className="text-2xs font-mono text-warning border border-warning/30 px-2 py-0.5 rounded">ACTIVE</span>;
}

// ─── Quick Start Tasks ───────────────────────────────────────────────────────

const QUICK_START = [
  { id: 'oom_crash', label: 'OOM Crash', fault: 'oom', diff: 2, desc: 'Restart crashed service' },
  { id: 'cascade_failure', label: 'Cascade', fault: 'cascade', diff: 3, desc: 'Scale from pool exhaustion' },
  { id: 'ghost_corruption', label: 'Ghost', fault: 'ghost', diff: 5, desc: 'Rollback silent corruption' },
  { id: 'ddos_flood', label: 'DDoS Flood', fault: 'network', diff: 3, desc: 'Scale API gateway' },
  { id: 'memory_spiral', label: 'Memory Spiral', fault: 'oom', diff: 4, desc: 'Restart memory leak' },
];

function DiffBadge({ d }: { d: number }) {
  const color = d <= 2 ? 'text-success' : d <= 3 ? 'text-warning' : 'text-danger';
  return <span className={`text-2xs font-mono border border-current/30 px-1.5 py-0.5 rounded ${color}`}>{d}</span>;
}

// ─── Main Dashboard Page ────────────────────────────────────────────────────

export function DashboardPage() {
  const navigate = useNavigate();
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [rewardHistory, setRewardHistory] = useState<Array<{ reward: number; cumulative_reward: number }>>([]);

  const { data: state, isLoading: stateLoading } = useQuery({
    queryKey: ['state'],
    queryFn: getState,
    refetchInterval: 5000,
  });

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
    refetchInterval: 10000,
  });

  const services: Record<string, Service> = state?.services ?? {};
  const alerts: Alert[] = state?.alerts ?? [];
  const slaDeadline: SlaDeadline | null = state?.sla_deadline ?? null;
  const businessImpact: BusinessImpact | null = state?.business_impact ?? null;
  const currentStep = state?.current_step ?? 0;
  const totalReward = state?.total_reward ?? 0;
  const faultType = state?.fault_type ?? null;
  const difficulty = state?.difficulty ?? null;
  const initialized = state?.initialized ?? false;
  const episodeDone = state?.episode_done ?? false;

  // Update reward history when step changes
  const prevStepRef = useRef(currentStep);
  useEffect(() => {
    if (currentStep !== prevStepRef.current) {
      prevStepRef.current = currentStep;
      if (initialized && currentStep > 0) {
        setRewardHistory(prev => {
          const last = prev[prev.length - 1];
          const newEntry = { reward: totalReward - (last?.cumulative_reward ?? 0), cumulative_reward: totalReward };
          return [...prev.slice(-49), newEntry];
        });
      }
    }
  }, [currentStep, totalReward, initialized]);

  const serviceList = Object.entries(services);
  const serviceNames = Object.keys(services);
  const criticalAlerts = alerts.filter(a => a.severity === 'critical' || a.severity === 'high');

  // Build metric history for sparklines (last 10 steps)
  const metricHistoryRef = useRef<Record<string, number[]>>({});
  useEffect(() => {
    for (const name of serviceNames) {
      const svc = services[name];
      if (!metricHistoryRef.current[`${name}_latency`]) {
        metricHistoryRef.current[`${name}_latency`] = [];
        metricHistoryRef.current[`${name}_error`] = [];
        metricHistoryRef.current[`${name}_cpu`] = [];
      }
      if (svc.latency_ms != null) metricHistoryRef.current[`${name}_latency`].push(svc.latency_ms);
      if (svc.error_rate != null) metricHistoryRef.current[`${name}_error`].push(svc.error_rate);
      if (svc.cpu_percent != null) metricHistoryRef.current[`${name}_cpu`].push(svc.cpu_percent);
      // Keep last 10 entries per metric
      const limit = 10;
      for (const key of [`${name}_latency`, `${name}_error`, `${name}_cpu`]) {
        if (metricHistoryRef.current[key].length > limit) {
          metricHistoryRef.current[key] = metricHistoryRef.current[key].slice(-limit);
        }
      }
    }
  }, [services, serviceNames]);

  const handleServiceClick = useCallback((name: string) => {
    setSelectedService(prev => prev === name ? null : name);
  }, []);

  const faultLabel = faultType
    ? `${faultType.replace(/_/g, ' ')}${difficulty ? ` (d=${difficulty})` : ''}`
    : 'No active incident';

  return (
    <div className="space-y-3">
      {/* ── Incident Banner ────────────────────────────────────────────────── */}
      <div className="panel">
        <div className="flex items-center gap-3 px-4 py-3">
          {/* Status indicator */}
          <span className={`w-2 h-2 rounded-full shrink-0 ${
            !initialized ? 'bg-text-muted' : episodeDone ? 'bg-success' : 'bg-warning'
          } ${initialized && !episodeDone ? 'critical-pulse' : ''}`} />

          {/* Fault label */}
          <span className="text-sm font-mono text-text-primary flex-1">
            {initialized ? faultLabel : 'No active incident — ready to begin'}
          </span>

          {/* SLA countdown */}
          {initialized && !episodeDone && (
            <div className="flex items-center gap-2 border-l border-border pl-3">
              <span className="text-2xs text-text-muted uppercase tracking-wider font-mono">SLA</span>
              <SlaCountdown deadline={slaDeadline} />
            </div>
          )}

          {/* Revenue loss */}
          {initialized && !episodeDone && businessImpact && (
            <div className="flex items-center gap-2 border-l border-border pl-3">
              <span className="text-2xs text-text-muted uppercase tracking-wider font-mono">$Loss</span>
              <RevenueCounter impact={businessImpact} />
            </div>
          )}

          {/* Step + reward */}
          {initialized && (
            <div className="flex items-center gap-4 border-l border-border pl-3">
              <div className="text-center">
                <div className="text-xs font-mono font-bold text-text-primary tabular-nums">{currentStep}</div>
                <div className="text-2xs text-text-muted font-mono uppercase tracking-wider">step</div>
              </div>
              <div className="text-center">
                <div className={`text-xs font-mono font-bold tabular-nums ${totalReward >= 0 ? 'text-success' : 'text-danger'}`}>
                  {totalReward >= 0 ? '+' : ''}{totalReward.toFixed(2)}
                </div>
                <div className="text-2xs text-text-muted font-mono uppercase tracking-wider">reward</div>
              </div>
            </div>
          )}

          {/* Status + action */}
          <div className="flex items-center gap-2 border-l border-border pl-3">
            <StatusBadge initialized={initialized} done={episodeDone} />
            <button
              onClick={() => navigate('/episode')}
              className="text-2xs font-mono text-accent hover:text-text-primary border border-accent/40 hover:border-accent/60 px-2 py-1 rounded transition-colors"
            >
              {initialized ? 'Continue →' : 'Start Episode'}
            </button>
          </div>
        </div>
      </div>

      {/* ── 4 Metric Cards ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {/* SLO Health */}
        <div className="panel px-4 py-3">
          <div className="text-2xs text-text-muted uppercase tracking-wider font-mono mb-1">SLO Health</div>
          <div className={`text-xl font-mono font-bold tabular-nums ${
            !state?.slo_metrics ? 'text-text-muted' :
            (state.slo_metrics.latency_slo_met && state.slo_metrics.error_slo_met) ? 'text-success' :
            'text-danger'
          }`}>
            {!state?.slo_metrics ? '--' :
              (state.slo_metrics.latency_slo_met && state.slo_metrics.error_slo_met) ? '✓ MET' : '✗ BREACH'}
          </div>
          {state?.slo_metrics && (
            <div className="text-2xs text-text-muted font-mono mt-0.5">
              {state.slo_metrics.availability_percent.toFixed(1)}% avail
            </div>
          )}
        </div>

        {/* SLA Time */}
        <div className="panel px-4 py-3">
          <div className="text-2xs text-text-muted uppercase tracking-wider font-mono mb-1">SLA Remaining</div>
          <div className={`text-xl font-mono font-bold tabular-nums ${
            !slaDeadline ? 'text-text-muted' :
            slaDeadline.urgency === 'critical' ? 'text-danger critical-pulse' :
            slaDeadline.urgency === 'elevated' ? 'text-warning' : 'text-text-primary'
          }`}>
            <SlaCountdown deadline={slaDeadline} />
          </div>
          {slaDeadline && (
            <div className="text-2xs text-text-muted font-mono mt-0.5">
              of {slaDeadline.sla_minutes}m SLA
            </div>
          )}
        </div>

        {/* Revenue Loss */}
        <div className="panel px-4 py-3">
          <div className="text-2xs text-text-muted uppercase tracking-wider font-mono mb-1">Revenue Lost</div>
          <div className="text-xl font-mono font-bold tabular-nums text-danger">
            ${!businessImpact ? '0.00' : businessImpact.cumulative_revenue_loss_usd.toFixed(2)}
          </div>
          {businessImpact && (
            <div className="text-2xs text-text-muted font-mono mt-0.5">
              ${businessImpact.revenue_loss_per_minute_usd.toFixed(2)}/min
            </div>
          )}
        </div>

        {/* Active Steps / Total */}
        <div className="panel px-4 py-3">
          <div className="text-2xs text-text-muted uppercase tracking-wider font-mono mb-1">Episode Progress</div>
          <div className="text-xl font-mono font-bold tabular-nums text-text-primary">
            {currentStep} <span className="text-text-muted text-base">/ {state?.max_steps ?? '?'}</span>
          </div>
          <div className="text-2xs text-text-muted font-mono mt-0.5">
            {alerts.length} alert{alerts.length !== 1 ? 's' : ''} · {serviceList.length} services
          </div>
        </div>
      </div>

      {/* ── Quick Start ─────────────────────────────────────────────────────── */}
      <div className="panel">
        <div className="panel-header">Quick Start</div>
        <div className="flex gap-2 p-3 overflow-x-auto scrollbar-thin">
          {QUICK_START.map(task => (
            <button
              key={task.id}
              onClick={() => navigate(`/episode?task=${task.id}`)}
              className="flex items-center gap-2 px-3 py-2 border border-border hover:border-accent/50 rounded text-xs transition-colors shrink-0"
            >
              <span className="text-text-primary font-mono">{task.label}</span>
              <DiffBadge d={task.diff} />
            </button>
          ))}
        </div>
      </div>

      {/* ── Split Grid: Services + Alerts ─────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Service Topology */}
        <div className="panel flex flex-col">
          <div className="panel-header flex items-center justify-between">
            <span>Services</span>
            <span className="text-text-muted font-mono normal-case tracking-normal">
              {serviceList.length} total
            </span>
          </div>

          {stateLoading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="h-8 rounded bg-bg animate-pulse" />
              ))}
            </div>
          ) : serviceList.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-text-muted">
              <span className="text-xs font-mono">No services — start an episode</span>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto">
              {/* Header row */}
              <div className="flex items-center gap-2 px-3 py-1 border-b border-border">
                <span className="w-2" />
                <span className="text-2xs font-mono text-text-muted flex-1">SERVICE</span>
                <span className="text-2xs font-mono text-text-muted">STATUS</span>
                <span className="text-2xs font-mono text-text-muted w-12 text-right">LAT</span>
                <span className="text-2xs font-mono text-text-muted w-10 text-right">ERR</span>
              </div>

              {serviceList.map(([name, svc]) => (
                <div key={name}>
                  <ServiceRow service={svc} onClick={handleServiceClick} />
                  {selectedService === name && (
                    <ServiceDetail
                      name={name}
                      service={svc}
                      history={metricHistoryRef.current}
                      onClose={() => setSelectedService(null)}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Alert Feed */}
        <div className="panel flex flex-col">
          <div className="panel-header flex items-center justify-between">
            <span>Alerts</span>
            {criticalAlerts.length > 0 && (
              <span className="text-2xs font-mono text-danger border border-danger/40 px-1.5 py-0.5 rounded critical-pulse">
                {criticalAlerts.length} critical
              </span>
            )}
            {alerts.length === 0 && initialized && (
              <span className="text-2xs font-mono text-success border border-success/40 px-1.5 py-0.5 rounded">✓ all clear</span>
            )}
          </div>

          {stateLoading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-10 rounded bg-bg animate-pulse" />
              ))}
            </div>
          ) : alerts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-text-muted">
              <span className="text-xs font-mono">No alerts</span>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto">
              {alerts.map(alert => (
                <AlertRow key={alert.id} alert={alert} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Action Stream ──────────────────────────────────────────────────── */}
      <div className="panel">
        <div className="panel-header flex items-center justify-between">
          <span>Action Stream</span>
          <div className="flex items-center gap-3">
            {/* Reward mini chart */}
            {rewardHistory.length > 1 && (
              <div className="w-32 h-8">
                <RewardChart actions={rewardHistory} />
              </div>
            )}
            <span className={`text-xs font-mono tabular-nums ${totalReward >= 0 ? 'text-success' : 'text-danger'}`}>
              Σ {totalReward >= 0 ? '+' : ''}{totalReward.toFixed(2)}
            </span>
          </div>
        </div>

        {rewardHistory.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-text-muted">
            <span className="text-xs font-mono">No actions yet — execute steps to see the stream</span>
          </div>
        ) : (
          <div className="overflow-y-auto max-h-48">
            {rewardHistory.map((entry, i) => (
              <ActionRow
                key={i}
                action={{
                  step: i + 1,
                  action_type: 'step',
                  target_service: '',
                  reward: entry.reward,
                  cumulative_reward: entry.cumulative_reward,
                }}
                index={i}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── Stats Bar ──────────────────────────────────────────────────────── */}
      <div className="panel px-4 py-3">
        <div className="flex items-center gap-6 text-xs font-mono">
          <div>
            <span className="text-text-muted">Episodes: </span>
            <span className="text-text-primary tabular-nums">{stats?.total_episodes ?? 0}</span>
          </div>
          <div>
            <span className="text-text-muted">Top Score: </span>
            <span className="text-success tabular-nums">{(stats?.top_score ?? 0).toFixed(3)}</span>
          </div>
          <div>
            <span className="text-text-muted">Avg Score: </span>
            <span className="text-text-primary tabular-nums">{(stats?.average_score ?? 0).toFixed(3)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
