import { create } from 'zustand';
import type { Observation, Service, Alert, SlaDeadline, BusinessImpact } from '../api/types';

interface EpisodeState {
  // Environment state
  initialized: boolean;
  currentStep: number;
  totalReward: number;
  faultType: string | null;
  difficulty: number | null;
  taskId: string | null;
  taskName: string | null;

  // Current observation
  observation: Observation | null;
  services: Record<string, Service>;
  alerts: Alert[];

  // Revenue & SLA
  slaDeadline: SlaDeadline | null;
  businessImpact: BusinessImpact | null;
  revenueLossStart: number | null;

  // Episode status
  episodeDone: boolean;
  episodeTruncated: boolean;
  episodeTerminated: boolean;

  // Action history
  actions: Array<{
    step: number;
    action_type: string;
    target_service: string;
    reward: number;
    cumulative_reward: number;
  }>;

  // UI state
  selectedService: string | null;
  selectedAction: string | null;

  // Actions
  setInitialized: (v: boolean) => void;
  setStep: (step: number, reward: number, faultType?: string, taskId?: string, taskName?: string) => void;
  setObservation: (observation: Observation) => void;
  addAction: (action_type: string, target_service: string, reward: number, cumulative_reward: number) => void;
  setSelectedService: (service: string | null) => void;
  setSelectedAction: (action: string | null) => void;
  reset: () => void;
}

const initialState = {
  initialized: false,
  currentStep: 0,
  totalReward: 0,
  faultType: null,
  difficulty: null,
  taskId: null,
  taskName: null,
  observation: null,
  services: {} as Record<string, Service>,
  alerts: [],
  slaDeadline: null,
  businessImpact: null,
  revenueLossStart: null,
  episodeDone: false,
  episodeTruncated: false,
  episodeTerminated: false,
  actions: [],
  selectedService: null,
  selectedAction: null,
};

export const useEpisodeStore = create<EpisodeState>((set) => ({
  ...initialState,

  setInitialized: (v) => set({ initialized: v }),

  setStep: (step, reward, faultType, taskId, taskName) =>
    set((s) => ({
      currentStep: step,
      totalReward: reward,
      faultType: faultType ?? s.faultType,
      taskId: taskId ?? s.taskId,
      taskName: taskName ?? s.taskName,
    })),

  setObservation: (observation) =>
    set({
      observation,
      services: observation.services as Record<string, Service>,
      alerts: observation.alerts,
      slaDeadline: observation.sla_deadline ?? null,
      businessImpact: observation.business_impact ?? null,
      episodeDone: observation.done || false,
      episodeTruncated: observation.truncated || false,
      episodeTerminated: observation.terminated || false,
    }),

  addAction: (action_type, target_service, reward, cumulative_reward) =>
    set((s) => ({
      actions: [
        ...s.actions,
        { step: s.actions.length + 1, action_type, target_service, reward, cumulative_reward },
      ],
    })),

  setSelectedService: (service) => set({ selectedService: service }),

  setSelectedAction: (action) => set({ selectedAction: action }),

  reset: () => set(initialState),
}));

// Auth Store
interface AuthState {
  isAuthenticated: boolean;
  username: string | null;
  token: string | null;
  apiKey: string | null;
  setAuth: (username: string, token: string, apiKey?: string) => void;
  setApiKey: (apiKey: string) => void;
  logout: () => void;
  loadFromStorage: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  username: null,
  token: null,
  apiKey: null,

  setAuth: (username, token, apiKey) => {
    localStorage.setItem('token', token);
    if (apiKey) {
      localStorage.setItem('apiKey', apiKey);
    }
    localStorage.setItem('username', username);
    set({ isAuthenticated: true, username, token, apiKey: apiKey ?? null });
  },

  setApiKey: (apiKey) => {
    localStorage.setItem('apiKey', apiKey);
    set({ apiKey });
  },

  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('apiKey');
    localStorage.removeItem('username');
    set({ isAuthenticated: false, username: null, token: null, apiKey: null });
  },

  loadFromStorage: () => {
    const token = localStorage.getItem('token');
    const apiKey = localStorage.getItem('apiKey');
    const username = localStorage.getItem('username');
    if (token && username) {
      set({ isAuthenticated: true, username, token, apiKey });
    }
  },
}));

// UI Store
interface UIState {
  sidebarOpen: boolean;
  authModalOpen: boolean;
  authModalCallback: (() => void) | null;
  toasts: Array<{ id: string; message: string; type: 'success' | 'error' | 'info' }>;
  toggleSidebar: () => void;
  openAuthModal: (callback: () => void) => void;
  closeAuthModal: () => void;
  addToast: (message: string, type: 'success' | 'error' | 'info') => void;
  removeToast: (id: string) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  authModalOpen: false,
  authModalCallback: null,
  toasts: [],

  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),

  openAuthModal: (callback) => set({ authModalOpen: true, authModalCallback: callback }),

  closeAuthModal: () => set({ authModalOpen: false, authModalCallback: null }),

  addToast: (message, type) => {
    const id = Math.random().toString(36).substring(7);
    set((s) => ({ toasts: [...s.toasts, { id, message, type }] }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, 4000);
  },

  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
