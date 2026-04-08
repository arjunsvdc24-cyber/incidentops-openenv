// API Types for IncidentOps Backend

export interface Service {
  name: string;
  status: 'healthy' | 'degraded' | 'down' | 'unhealthy' | 'unknown';
  latency_ms?: number;
  error_rate?: number;
  cpu_percent?: number;
  memory_percent?: number;
  requests_per_sec?: number;
  metrics?: Record<string, number | string>;
}

export interface SlaMetrics {
  availability_percent: number;
  latency_p99_ms: number;
  latency_slo_met: boolean;
  error_rate_percent: number;
  error_slo_met: boolean;
  error_budget_remaining_percent: number;
  healthy_services: number;
  degraded_services: number;
  unhealthy_services: number;
}

export interface BusinessImpact {
  revenue_loss_per_minute_usd: number;
  cumulative_revenue_loss_usd: number;
  affected_users_estimate: number;
  impacted_services: string[];
  severity: 'normal' | 'warning' | 'critical';
}

export interface SlaDeadline {
  sla_minutes: number;
  minutes_remaining: number;
  urgency: 'normal' | 'elevated' | 'critical';
  sla_breached: boolean;
  sla_target_minutes: number;
}

export interface Observation {
  timestamp: string;
  step?: number;
  services: Record<string, Service>;
  alerts: Alert[];
  logs: LogEntry[];
  metrics: Record<string, number>;
  incident_info?: { fault_type: string; difficulty: number } | null;
  fix_applied?: boolean;
  observability?: { observed_services: number; observed_logs: number; observed_metrics: number };
  slo_metrics?: SlaMetrics;
  business_impact?: BusinessImpact;
  sla_deadline?: SlaDeadline;
  message: string;
  done: boolean;
  truncated: boolean;
  terminated: boolean;
  info?: Record<string, unknown>;
  warning?: string;
  error?: string;
  action_result?: Record<string, unknown>;
}

export interface Alert {
  id: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info' | 'warning' | 'error';
  service: string;
  message: string;
  timestamp: string;
}

export interface LogEntry {
  service: string;
  level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG';
  message: string;
  timestamp: string;
}

export interface ActionType {
  name: string;
  description: string;
  requires_target: boolean;
}

export interface Task {
  id: string;
  name: string;
  difficulty: 1 | 2 | 3 | 4 | 5;
  fault_type: string;
  description: string;
  services_affected: string[];
  difficulty_label: string;
  hints?: string[];
  expected_min_steps?: number;
  expected_max_steps?: number;
}

export interface StepRequest {
  action_type: string;
  target_service?: string;
  task_id?: string;
}

export interface StepResponse {
  observation: Observation;
  reward: number;
  cumulative_reward: number;
  episode_complete: boolean;
  episode_truncated: boolean;
  episode_terminated: boolean;
  action_type: string;
  target_service: string;
  timestamp: string;
}

export interface ResetResponse {
  observation: Observation;
  task_id: string | null;
  fault_type: string | null;
  episode_started: boolean;
}

export interface State {
  initialized: boolean;
  current_step: number;
  total_reward: number;
  fault_type: string | null;
  difficulty: number | null;
  services: Record<string, Service>;
  alerts: Alert[];
  episode_done: boolean;
  episode_truncated: boolean;
  episode_terminated: boolean;
  max_steps?: number;
  scenario?: { fault_type: string; difficulty: number } | null;
  slo_metrics?: SlaMetrics;
  business_impact?: BusinessImpact;
  sla_deadline?: SlaDeadline;
  information_summary?: string;
  reasoning_score?: number;
  is_guessing?: boolean;
}

export interface Stats {
  total_episodes: number;
  active_episodes: number;
  average_score: number;
  top_score: number;
  recent_activity: ActivityEntry[];
}

export interface ActivityEntry {
  id?: string;
  action_type: string;
  target_service: string;
  reward: number;
  timestamp: string;
  fault_type: string;
}

export interface GradeResult {
  trajectory_score: number;
  max_score: number;
  percentage: number;
  breakdown: {
    effectiveness: number;
    efficiency: number;
    accuracy: number;
    safety: number;
    thoroughness: number;
  };
  feedback: string;
}

export interface Episode {
  id: string;
  episode_id?: string;
  fault_type: string;
  task_id: string;
  task_name: string;
  score: number;
  grade: number;
  steps: number;
  trajectory: TrajectoryEntry[];
  created_at: string;
  username?: string;
}

export interface TrajectoryEntry {
  step: number;
  action_type: string;
  target_service: string;
  observation: Observation;
  reward: number;
  cumulative_reward: number;
}

export interface LeaderboardEntry {
  rank: number;
  username: string;
  task_id: string;
  task_name: string;
  best_score: number;
  avg_score: number;
  episode_count: number;
  updated_at: string;
}

export interface UserProfile {
  username: string;
  api_key: string;
  total_episodes: number;
  best_scores: Record<string, number>;
  leaderboard_ranks: Record<string, number>;
}

export interface ConfigureRequest {
  seed?: number;
  difficulty?: number;
  task_id?: string;
}

export interface ValidationResult {
  name: string;
  passed: boolean;
  message: string;
}

export interface FrontierTask {
  task_id: string;
  name: string;
  difficulty: number;
  fault_type: string;
  description: string;
  services_affected: string[];
}

export interface AuthResponse {
  success: boolean;
  token?: string;
  username?: string;
  message?: string;
}

export interface WsMessage {
  type: 'episode_start' | 'step_executed' | 'score_recorded' | 'pong';
  [key: string]: unknown;
}
