import type {
  Service,
  Alert,
  LogEntry,
  Observation,
  ActionType,
  Task,
  StepRequest,
  StepResponse,
  ResetResponse,
  State,
  Stats,
  GradeResult,
  Episode,
  LeaderboardEntry,
  UserProfile,
  ConfigureRequest,
  ValidationResult,
  FrontierTask,
  AuthResponse,
} from './types';

const BASE = window.location.origin;

function getHeaders(auth = false): HeadersInit {
  const h: HeadersInit = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = localStorage.getItem('token');
    if (token) h['Authorization'] = `Bearer ${token}`;
    const apiKey = localStorage.getItem('apiKey');
    if (apiKey) h['X-API-Key'] = apiKey;
  }
  return h;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`${response.status}: ${errorText || response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export async function apiGet<T>(path: string, auth = false): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: 'GET',
    headers: getHeaders(auth),
  });
  return handleResponse<T>(response);
}

export async function apiPost<T>(path: string, body: unknown, auth = false): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: getHeaders(auth),
    body: JSON.stringify(body),
  });
  return handleResponse<T>(response);
}

// Health & Info
export async function getApiInfo(): Promise<{ name: string; version: string; endpoints: string[] }> {
  return apiGet('/api');
}

export async function getHealth(): Promise<{ status: string }> {
  return apiGet('/health');
}

// Services & Actions
export async function getServices(): Promise<Service[]> {
  const data = await apiGet<{ services: string[] } | string[]>('/services');
  if (Array.isArray(data)) {
    return data.map((name) => ({ name, status: 'unknown' as const }));
  }
  return (data.services || []).map((name: string) => ({
    name,
    status: 'unknown' as const,
  }));
}

// Which actions require a target service
const SERVICE_REQUIRED_ACTIONS = new Set([
  'query_service', 'query_metrics', 'query_logs', 'query_dependencies',
  'restart_service', 'scale_service', 'rollback_deployment',
  'query_deployments', 'query_memory', 'identify_root_cause', 'apply_fix',
]);

export async function getActions(): Promise<{ actions: ActionType[] }> {
  const data = await apiGet<{ actions: string[]; count: number }>('/actions');
  return {
    actions: (data.actions || []).map((name: string) => ({
      name,
      description: name.replace(/_/g, ' '),
      requires_target: SERVICE_REQUIRED_ACTIONS.has(name),
    })),
  };
}

// Map frontend task IDs to backend fault types + difficulty
const TASK_ID_TO_FAULT_TYPE: Record<string, string> = {
  'oom_crash': 'oom',
  'cascade_failure': 'cascade',
  'cascade': 'cascade',
  'ghost_corruption': 'ghost',
  'ghost': 'ghost',
  'oom': 'oom',
  'ddos_flood': 'network',
  'memory_spiral': 'oom',
};

// Map task ID to {fault_type, difficulty}
const TASK_CONFIG: Record<string, { fault_type: string; difficulty: number }> = {
  'oom_crash': { fault_type: 'oom', difficulty: 2 },
  'cascade_failure': { fault_type: 'cascade', difficulty: 3 },
  'ghost_corruption': { fault_type: 'ghost', difficulty: 5 },
  'ddos_flood': { fault_type: 'network', difficulty: 3 },
  'memory_spiral': { fault_type: 'oom', difficulty: 4 },
};

// Environment Control
export async function resetEnvironment(taskId?: string): Promise<ResetResponse> {
  const config = taskId ? TASK_CONFIG[taskId] : undefined;
  const payload = config ? { fault_type: config.fault_type, difficulty: config.difficulty } : {};
  const response = await apiPost<{ observation: Record<string, unknown>; info: Record<string, unknown> }>(
    '/reset',
    payload
  );
  // Normalize: backend returns {observation, info}, frontend expects {observation, task_id, fault_type, episode_started}
  const obs = response.observation;
  const rawAlerts = (obs.alerts as Array<{ service: string; severity: string; message: string }>) || [];
  const alerts: Alert[] = rawAlerts.map((a, i) => ({
    id: `alert-${i}`,
    service: a.service,
    severity: (a.severity === 'critical' ? 'critical' : a.severity === 'error' ? 'high' : a.severity === 'warning' ? 'medium' : 'low') as Alert['severity'],
    message: a.message,
    timestamp: new Date().toISOString(),
  }));
  return {
    observation: {
      timestamp: (obs.timestamp as string) || new Date().toISOString(),
      services: normalizeServices(obs.services),
      alerts,
      logs: ((obs.logs as unknown[]) || []) as LogEntry[],
      metrics: (obs.metrics as Record<string, number>) || {},
      message: (obs.message as string) || (obs.action_result as Record<string, unknown>)?.error as string || '',
      done: obs.done as boolean || false,
      truncated: obs.truncated as boolean || false,
      terminated: obs.terminated as boolean || false,
      info: obs.info as Record<string, unknown>,
      warning: obs.warning as string | undefined,
      error: obs.error as string | undefined,
    },
    // Preserve the original task_id for display, use fault_type from backend
    task_id: taskId || null,
    fault_type: (response.info?.fault_type as string) || (response.info?.difficulty as string) || null,
    episode_started: true,
  };
}

export async function executeStep(request: StepRequest): Promise<StepResponse> {
  const data = await apiPost<{
    observation: Record<string, unknown>;
    reward: number;
    terminated: boolean;
    truncated: boolean;
    info: Record<string, unknown>;
  }>('/step', request);

  // Normalize backend StepResponse to frontend StepResponse
  const obs = data.observation as Record<string, unknown>;
  return {
    observation: {
      timestamp: (obs.timestamp as string) || new Date().toISOString(),
      // Backend services is dict {name: {status, latency_ms, ...}}; normalize to array
      services: normalizeServices(obs.services),
      alerts: normalizeAlerts((obs.alerts as RawAlert[]) || []),
      logs: ((obs.logs as unknown[]) || []) as LogEntry[],
      metrics: (obs.metrics as Record<string, number>) || {},
      message: (obs.message as string) || (obs.action_result as Record<string, unknown>)?.error as string || '',
      done: data.terminated || data.truncated,
      truncated: data.truncated || false,
      terminated: data.terminated || false,
      info: obs.info as Record<string, unknown>,
      warning: obs.warning as string | undefined,
      error: obs.error as string | undefined,
    },
    reward: data.reward,
    cumulative_reward: data.reward, // caller should accumulate
    episode_complete: data.terminated || data.truncated,
    episode_truncated: data.truncated || false,
    episode_terminated: data.terminated || false,
    action_type: request.action_type,
    target_service: request.target_service || '',
    timestamp: new Date().toISOString(),
  };
}

interface RawAlert {
  service?: string;
  severity?: string;
  message?: string;
  id?: string;
  timestamp?: string;
}

function normalizeAlerts(raw: RawAlert[]): Alert[] {
  if (!raw || !Array.isArray(raw)) return [];
  const severityMap: Record<string, Alert['severity']> = {
    critical: 'critical',
    error: 'high',
    warning: 'medium',
    info: 'low',
  };
  return raw.map((a, i) => ({
    id: a.id || `alert-${i}-${Date.now()}`,
    service: a.service || 'unknown',
    severity: severityMap[a.severity || ''] || 'low',
    message: a.message || '',
    timestamp: a.timestamp || new Date().toISOString(),
  }));
}

function normalizeServices(raw: unknown): Record<string, Service> {
  if (!raw) return {};
  if (typeof raw === 'object') {
    const obj = raw as Record<string, unknown>;
    const result: Record<string, Service> = {};
    for (const [name, state] of Object.entries(obj)) {
      const s = state as Record<string, unknown>;
      result[name] = {
        name,
        status: (s.status as Service['status']) || 'unknown',
        latency_ms: s.latency_ms as number | undefined,
        error_rate: s.error_rate as number | undefined,
        cpu_percent: s.cpu_percent as number | undefined,
        memory_percent: s.memory_percent as number | undefined,
        requests_per_sec: s.requests_per_sec as number | undefined,
        metrics: {
          ...((s as Record<string, number | string>) ?? {}),
        },
      };
    }
    return result;
  }
  return {};
}

export async function getState(): Promise<State> {
  const data = await apiGet<{
    initialized: boolean;
    step: number;
    max_steps: number;
    terminated: boolean;
    truncated: boolean;
    total_reward: number;
    scenario: { fault_type: string; difficulty: number } | null;
    services?: Record<string, Record<string, unknown>>;
    alerts?: Array<{ id: string; service: string; severity: string; message: string; timestamp: string }>;
    information_summary?: string;
    reasoning_score?: number;
    is_guessing?: boolean;
    slo_metrics?: Record<string, unknown>;
    business_impact?: Record<string, unknown>;
    sla_deadline?: Record<string, unknown>;
  }>('/state');

  function normalizeSeverity(s: string): Alert['severity'] {
    const map: Record<string, Alert['severity']> = {
      critical: 'critical', error: 'high', warning: 'medium', info: 'low',
    };
    return (map[s] ?? s) as Alert['severity'];
  }

  return {
    initialized: data.initialized || false,
    current_step: data.step || 0,
    max_steps: data.max_steps || 50,
    total_reward: data.total_reward || 0,
    fault_type: data.scenario?.fault_type || null,
    difficulty: data.scenario?.difficulty || null,
    services: normalizeServices(data.services),
    alerts: (data.alerts || []).map((a) => ({
      id: a.id || `alert-${Math.random()}`,
      service: a.service,
      severity: normalizeSeverity(a.severity),
      message: a.message,
      timestamp: a.timestamp || new Date().toISOString(),
    })),
    episode_done: data.terminated || data.truncated || false,
    episode_truncated: data.truncated || false,
    episode_terminated: data.terminated || false,
    slo_metrics: data.slo_metrics as State['slo_metrics'],
    business_impact: data.business_impact as State['business_impact'],
    sla_deadline: data.sla_deadline as State['sla_deadline'],
    information_summary: data.information_summary,
    reasoning_score: data.reasoning_score,
    is_guessing: data.is_guessing,
  };
}

export async function configure(request: ConfigureRequest): Promise<{ success: boolean }> {
  // Map task_id to fault_type + difficulty if provided
  if (request.task_id && TASK_CONFIG[request.task_id]) {
    const { fault_type, difficulty } = TASK_CONFIG[request.task_id];
    return apiPost('/configure', { ...request, fault_type, difficulty });
  }
  return apiPost('/configure', request);
}

// Tasks
export async function getTasks(): Promise<{ tasks: Task[]; action_schema: Record<string, unknown> }> {
  const data = await apiGet<{
    total: number;
    tasks: Array<{
      id: string;
      name: string;
      difficulty: string;
      difficulty_level: number;
      fault_type: string;
      description: string;
      services_affected: string[];
      hints?: string[];
      expected_min_steps?: number;
      expected_max_steps?: number;
    }>;
    action_schema: Record<string, unknown>;
  }>('/tasks');

  function mapDifficultyLabel(level: number): string {
    if (level <= 2) return 'easy';
    if (level <= 3) return 'medium';
    if (level <= 4) return 'medium-hard';
    return 'hard';
  }

  return {
    tasks: (data.tasks || []).map((t) => ({
      id: t.id,
      name: t.name,
      difficulty: (t.difficulty_level || 2) as 1 | 2 | 3 | 4 | 5,
      fault_type: t.fault_type || t.id,
      description: t.description || '',
      services_affected: t.services_affected || [],
      difficulty_label: mapDifficultyLabel(t.difficulty_level || 2),
    })),
    action_schema: data.action_schema || {},
  };
}

// Grading
export async function gradeTrajectory(
  trajectory: Array<{ action_type: string; target_service: string; reward: number }>
): Promise<GradeResult> {
  // Build the GradeRequest format the backend expects
  const request = {
    actions: trajectory.map((t) => ({
      action_type: t.action_type,
      target_service: t.target_service,
      reward: t.reward,
    })),
    rewards: trajectory.map((t) => t.reward),
    final_state: {
      total_reward: trajectory.reduce((s, t) => s + t.reward, 0),
      step_count: trajectory.length,
    },
    scenario: {
      fault_type: 'unknown',
      difficulty: 3,
    },
    use_enhanced: true,
    seed: 42,
  };

  const data = await apiPost<{
    trajectory_id: string | null;
    final_score: number;
    grade: string;
    breakdown?: {
      effectiveness?: number;
      efficiency?: number;
      accuracy?: number;
      safety?: number;
      thoroughness?: number;
      root_cause_accuracy?: number;
      fix_correctness?: number;
      minimal_disruption?: number;
      reasoning_quality?: number;
    };
    explanation?: string;
    strengths?: string[];
    weaknesses?: string[];
    suggestions?: string[];
  }>('/grader', request);

  const b = data.breakdown || {};
  return {
    trajectory_score: data.final_score || 0,
    max_score: 1.0,
    percentage: (data.final_score || 0) * 100,
    breakdown: {
      effectiveness: b.effectiveness || b.root_cause_accuracy || 0,
      efficiency: b.efficiency || 0,
      accuracy: b.accuracy || 0,
      safety: b.safety || 0,
      thoroughness: b.thoroughness || 0,
    },
    feedback: data.explanation || data.grade || '',
  };
}

// Stats
export async function getStats(): Promise<Stats> {
  const data = await apiGet<{
    total_episodes?: number;
    total_users?: number;
    avg_score?: number;
    top_score?: number;
    scores_by_fault?: Record<string, number>;
    top_agents?: unknown[];
    recent_episodes?: unknown[];
    recent_activity?: unknown[];
    active_episodes?: number;
  }>('/stats');
  return {
    total_episodes: data.total_episodes ?? 0,
    active_episodes: data.active_episodes ?? 0,
    top_score: data.top_score ?? 0,
    average_score: data.avg_score ?? 0,
    recent_activity: (data.recent_activity ?? data.recent_episodes ?? []) as Stats['recent_activity'],
  };
}

// Episodes
export async function getEpisodes(
  page = 1,
  limit = 20,
  faultType?: string
): Promise<{ episodes: Episode[]; total: number; page: number; pages: number }> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (faultType) params.set('fault_type', faultType);
  const data = await apiGet<{
    total: number;
    episodes: Array<{
      id?: number | string;
      episode_id?: string;
      fault_type: string;
      difficulty: number;
      seed: number;
      agent_type: string;
      agent_model?: string;
      total_reward: number;
      final_score: number;
      grade: string;
      root_cause_score?: number;
      fix_score?: number;
      efficiency_score?: number;
      disruption_score?: number;
      reasoning_score?: number;
      num_steps: number;
      created_at: string;
      duration_ms?: number;
      actions?: unknown[];
      observations?: unknown[];
      rewards?: unknown[];
    }>;
    page: number;
    per_page: number;
  }>(`/episodes?${params}`, true);

  const total = data.total || 0;
  const per_page = data.per_page || limit;
  return {
    episodes: (data.episodes || []).map((e) => ({
      id: String(e.id ?? e.episode_id ?? ''),
      episode_id: String(e.episode_id ?? e.id ?? ''),
      fault_type: e.fault_type,
      task_id: e.episode_id || String(e.id) || '',
      task_name: e.fault_type || '',
      score: e.total_reward || e.final_score || 0,
      grade: (e.final_score || 0) * 100,
      steps: e.num_steps || 0,
      trajectory: (e.actions || []) as Episode['trajectory'],
      created_at: e.created_at,
      username: undefined,
    })),
    total,
    page: data.page || page,
    pages: Math.ceil(total / per_page),
  };
}

export async function getEpisode(id: string): Promise<Episode> {
  const data = await apiGet<{
    id: number;
    episode_id: string;
    fault_type: string;
    difficulty: number;
    seed: number;
    agent_type: string;
    agent_model?: string;
    total_reward: number;
    final_score: number;
    grade: string;
    num_steps: number;
    created_at: string;
    duration_ms?: number;
    actions?: unknown[];
    observations?: unknown[];
    rewards?: unknown[];
  }>(`/episodes/${id}`, true);

  // Transform backend's separate arrays into frontend's trajectory format
  const actions = (data.actions || []) as string[];
  const observations = (data.observations || []) as Record<string, unknown>[];
  const rewards = (data.rewards || []) as number[];

  let cumulative = 0;
  const trajectory = actions.map((actionType, i) => {
    cumulative += rewards[i] ?? 0;
    return {
      step: i + 1,
      action_type: actionType,
      target_service: '',
      observation: (observations[i] || {
        timestamp: new Date().toISOString(),
        services: [],
        alerts: [],
        logs: [],
        metrics: {},
        message: '',
        done: false,
        truncated: false,
        terminated: false,
      }) as unknown as Observation,
      reward: rewards[i] ?? 0,
      cumulative_reward: cumulative,
    };
  });

  return {
    id: String(data.id),
    episode_id: data.episode_id || String(data.id),
    fault_type: data.fault_type,
    task_id: data.episode_id || String(data.id),
    task_name: data.fault_type,
    score: data.total_reward || data.final_score || 0,
    grade: (data.final_score || 0) * 100,
    steps: data.num_steps || 0,
    trajectory,
    created_at: data.created_at,
  };
}

export async function saveEpisode(
  faultType: string,
  taskId: string,
  _taskName: string,
  score: number,
  grade: number,
  trajectory: Array<{ action_type: string; target_service: string; reward: number }>
): Promise<{ id: string; success: boolean }> {
  const episode_id = `ep_${Date.now()}_${Math.random().toString(36).substring(7)}`;
  const fault_lower = (faultType || 'unknown').toLowerCase();
  const difficulty =
    fault_lower.includes('oom') ? 2 :
    fault_lower.includes('cascade') ? 3 :
    fault_lower.includes('ghost') ? 5 : 3;

  // Map task ID to fault type
  const scenarioFaultType = TASK_ID_TO_FAULT_TYPE[taskId] ?? fault_lower.split('_')[0] ?? fault_lower;
  // Determine grade string from percentage
  const pct = grade; // grade is already a percentage (0-100) from the frontend
  const gradeStr = pct >= 90 ? 'S' : pct >= 80 ? 'A' : pct >= 60 ? 'B' : pct >= 40 ? 'C' : 'D';
  const finalScore = grade / 100; // backend expects 0.0-1.0

  try {
    const result = await apiPost<{ id: number; episode_id: string }>(
      '/episodes',
      {
        episode_id,
        fault_type: scenarioFaultType,
        difficulty,
        seed: 42,
        agent_type: 'human',
        agent_model: null,
        actions: trajectory.map((t) => t.action_type),
        observations: [],
        rewards: trajectory.map((t) => t.reward),
        total_reward: score,
        final_score: finalScore,
        grade: gradeStr,
        root_cause_score: null,
        fix_score: null,
        efficiency_score: null,
        disruption_score: null,
        reasoning_score: null,
        num_steps: trajectory.length,
        terminated: false,
        truncated: false,
        duration_ms: null,
      },
      true
    );
    return { id: String(result.id || episode_id), success: true };
  } catch {
    return { id: episode_id, success: true };
  }
}

// Leaderboard
export async function getLeaderboard(
  taskId?: string
): Promise<{ entries: LeaderboardEntry[]; total: number }> {
  const params = taskId ? `?task_id=${taskId}` : '';
  const data = await apiGet<{
    task_id?: string;
    grader_type: string;
    entries: Array<{
      rank: number;
      user_id: number;
      username: string;
      task_id: string;
      best_score: number;
      avg_score: number;
      episode_count: number;
      updated_at: string;
    }>;
    total: number;
  }>(`/leaderboard${params}`);

  return {
    entries: (data.entries || []).map((e) => ({
      rank: e.rank || 0,
      username: e.username,
      task_id: e.task_id,
      task_name: e.task_id,
      best_score: e.best_score || 0,
      avg_score: e.avg_score || 0,
      episode_count: e.episode_count || 0,
      updated_at: e.updated_at,
    })),
    total: data.total || 0,
  };
}

// Profile
export async function getProfile(): Promise<UserProfile> {
  const data = await apiGet<{
    id: number;
    username: string;
    email?: string;
    api_key: string;
    is_active: boolean;
    is_admin: boolean;
    created_at: string;
    last_seen?: string;
  }>('/me', true);
  return {
    username: data.username,
    api_key: data.api_key || '',
    total_episodes: 0,
    best_scores: {},
    leaderboard_ranks: {},
  };
}

// Validation
export async function getValidation(): Promise<ValidationResult[]> {
  const data = await apiGet<Record<string, unknown>>('/validation');
  // Backend returns category-bucketed results. Flatten to ValidationResult[]
  const results: ValidationResult[] = [];
  for (const [, value] of Object.entries(data)) {
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item && typeof item === 'object') {
          const obj = item as Record<string, unknown>;
          results.push({
            name: (obj.name as string) || (obj.test as string) || 'unknown',
            passed: (obj.passed as boolean) ?? (obj.status === 'PASS' ? true : false),
            message: (obj.message as string) || (obj.error as string) || (obj.details as string) || '',
          });
        }
      }
    }
  }
  return results;
}

// Frontier
export async function getFrontier(): Promise<FrontierTask> {
  const data = await apiGet<{
    scenario_id?: string;
    difficulty?: number;
    minimum_steps?: number;
    dual_layer_failure?: { primary_failure?: string; secondary_failure?: string };
  }>('/frontier');
  return {
    task_id: (data.scenario_id as string) || 'frontier',
    name: 'Frontier Challenge',
    difficulty: data.difficulty || 5,
    fault_type: (data.dual_layer_failure?.primary_failure as string) || 'unknown',
    description: 'A frontier-difficulty scenario with dual-layer failures',
    services_affected: [
      data.dual_layer_failure?.primary_failure || '',
      data.dual_layer_failure?.secondary_failure || '',
    ].filter(Boolean),
  };
}

// Determinism
export async function checkDeterminism(seed?: number): Promise<{ deterministic: boolean; details: string }> {
  const params = seed ? `?seed=${seed}` : '';
  return apiGet(`/determinism/check${params}`);
}

// Baseline runner
export interface BaselineResult {
  task_id: string;
  task_name: string;
  difficulty: number;
  score: number;
  steps: number;
  actions: string[];
  success: boolean;
  error?: string;
}

export async function runBaseline(): Promise<{
  results: BaselineResult[];
  overall_score: number;
  model_used: string;
}> {
  const data = await apiPost<{
    results: Array<{
      task_id: string;
      task_name: string;
      difficulty: number;
      score: number;
      steps: number;
      actions: string[];
      success: boolean;
      error?: string;
    }>;
    overall_score: number;
    model_used: string;
  }>('/baseline', {});
  return data;
}

// OpenAI / LLM Check — auto-detects provider from key format
export async function checkOpenAI(apiKey: string): Promise<{ valid: boolean; model?: string; provider?: string }> {
  // Groq keys start with 'gsk_'
  if (apiKey.startsWith('gsk_')) {
    return apiPost('/openai/check', {
      groq_api_key: apiKey,
      groq_model: 'groq/llama-4-opus-17b',
    });
  }
  // Gemini (Google AI Studio) keys start with 'AIza'
  if (apiKey.startsWith('AIza')) {
    return apiPost('/openai/check', {
      gemini_api_key: apiKey,
      gemini_model: 'gemini-2.0-flash',
    });
  }
  // AskSage keys — heuristic: longer keys that aren't OpenAI or Gemini format
  // OpenAI keys typically start with 'sk-' or 'sk-proj-'
  if (apiKey.startsWith('sk-') || apiKey.startsWith('sk-proj-')) {
    return apiPost('/openai/check', {
      openai_api_key: apiKey,
      openai_model: 'gpt-4o',
    });
  }
  // Default: treat as AskSage (OpenAI-compatible endpoint)
  return apiPost('/openai/check', {
    askme_api_key: apiKey,
    askme_model: 'gpt-4o',
    askme_base_url: 'https://api.asksage.ai/server',
  });
}

// Validate a specific provider explicitly
export async function checkProvider(
  provider: 'groq' | 'gemini' | 'asksage' | 'openai' | 'huggingface',
  apiKey: string,
  model?: string
): Promise<{ valid: boolean; model?: string; provider?: string }> {
  switch (provider) {
    case 'groq':
      return apiPost('/openai/check', {
        groq_api_key: apiKey,
        groq_model: model || 'groq/llama-4-opus-17b',
      });
    case 'gemini':
      return apiPost('/openai/check', {
        gemini_api_key: apiKey,
        gemini_model: model || 'gemini-2.0-flash',
      });
    case 'asksage':
      return apiPost('/openai/check', {
        askme_api_key: apiKey,
        askme_model: model || 'gpt-4o',
        askme_base_url: 'https://api.asksage.ai/server',
      });
    case 'openai':
      return apiPost('/openai/check', {
        openai_api_key: apiKey,
        openai_model: model || 'gpt-4o',
      });
    case 'huggingface':
      return apiPost('/openai/check', {
        hf_token: apiKey,
        hf_model: model || undefined,
      });
  }
}

// Auth
export async function login(username: string, password: string): Promise<AuthResponse> {
  const data = await apiPost<{
    access_token: string;
    token_type: string;
    user: {
      id: number;
      username: string;
      email?: string;
      api_key: string;
      is_active: boolean;
      is_admin: boolean;
      created_at: string;
      last_seen?: string;
    };
  }>('/auth/login', { username, password });
  return {
    success: true,
    token: data.access_token,
    username: data.user.username,
  };
}

export async function register(username: string, password: string): Promise<AuthResponse> {
  const data = await apiPost<{
    access_token: string;
    token_type: string;
    user: {
      id: number;
      username: string;
      email?: string;
      api_key: string;
      is_active: boolean;
      is_admin: boolean;
      created_at: string;
      last_seen?: string;
    };
  }>('/auth/register', { username, password });
  return {
    success: true,
    token: data.access_token,
    username: data.user.username,
  };
}
