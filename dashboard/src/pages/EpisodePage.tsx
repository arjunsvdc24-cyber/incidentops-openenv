import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  resetEnvironment,
  executeStep,
  getActions,
  getTasks,
  saveEpisode,
  gradeTrajectory,
} from '../api/client';
import { useEpisodeStore, useAuthStore, useUIStore } from '../stores/episodeStore';
import { ActionPanel } from '../components/ActionPanel';
import { ObservationViewer } from '../components/ObservationViewer';
import { RewardDisplay } from '../components/RewardDisplay';
import { Timeline } from '../components/Timeline';
import { ServiceGrid } from '../components/ServiceGrid';
import { AlertList } from '../components/AlertList';

export function EpisodePage() {
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { isAuthenticated } = useAuthStore();
  const { openAuthModal, addToast } = useUIStore();
  const {
    initialized,
    currentStep,
    totalReward,
    faultType,
    taskId,
    taskName,
    observation,
    services,
    alerts,
    episodeDone,
    episodeTruncated,
    episodeTerminated,
    actions,
    selectedService,
    selectedAction,
    setInitialized,
    setStep,
    setObservation,
    addAction,
    setSelectedService,
    setSelectedAction,
    reset,
  } = useEpisodeStore();

  const [executing, setExecuting] = useState(false);
  const [initializing, setInitializing] = useState(false);

  const { data: actionsData } = useQuery({
    queryKey: ['actions'],
    queryFn: getActions,
  });

  const { data: tasksData } = useQuery({
    queryKey: ['tasks'],
    queryFn: getTasks,
  });

  const resetMutation = useMutation({
    mutationFn: async (taskId?: string) => {
      setInitializing(true);
      try {
        const response = await resetEnvironment(taskId);
        return response;
      } finally {
        setInitializing(false);
      }
    },
    onSuccess: (data) => {
      if (data.episode_started) {
        setInitialized(true);
        setStep(0, 0, data.fault_type ?? undefined, data.task_id ?? undefined);
        setObservation(data.observation);
        addToast(`Episode started: ${data.fault_type || 'Random fault'}`, 'success');
      }
    },
    onError: (error) => {
      addToast(`Failed to start episode: ${error}`, 'error');
    },
  });

  const stepMutation = useMutation({
    mutationFn: async () => {
      if (!selectedAction) throw new Error('No action selected');
      setExecuting(true);
      try {
        const response = await executeStep({
          action_type: selectedAction,
          target_service: selectedService || undefined,
        });
        return response;
      } finally {
        setExecuting(false);
      }
    },
    onSuccess: (data) => {
      setStep(currentStep + 1, totalReward + data.reward, faultType ?? undefined, taskId ?? undefined, taskName ?? undefined);
      setObservation(data.observation);
      addAction(selectedAction!, selectedService || '', data.reward, totalReward + data.reward);
      if (data.observation.done || data.observation.terminated || data.observation.truncated) {
        addToast('Episode ended', 'info');
      }
    },
    onError: (error) => {
      addToast(`Action failed: ${error}`, 'error');
    },
  });

  const handleStartEpisode = (selectedTaskId?: string) => {
    reset();
    resetMutation.mutate(selectedTaskId || searchParams.get('task') || undefined);
  };

  const handleExecuteAction = () => {
    if (!initialized) {
      addToast('Please start an episode first', 'error');
      return;
    }
    if (!selectedAction) {
      addToast('Please select an action', 'error');
      return;
    }
    const actionDef = actionsData?.actions?.find((a) => a.name === selectedAction);
    if (actionDef?.requires_target && !selectedService) {
      addToast('Please select a target service', 'error');
      return;
    }
    stepMutation.mutate();
  };

  const handleSaveEpisode = async () => {
    if (!isAuthenticated) {
      openAuthModal(() => handleSaveEpisode());
      return;
    }

    if (actions.length === 0) {
      addToast('No actions to save', 'error');
      return;
    }

    try {
      const trajectory = actions.map((a) => ({
        action_type: a.action_type,
        target_service: a.target_service,
        reward: a.reward,
      }));

      const gradeResult = await gradeTrajectory(trajectory);
      await saveEpisode(
        faultType || 'unknown',
        taskId || 'unknown',
        taskName || 'Unknown Task',
        totalReward,
        gradeResult.percentage,
        trajectory
      );
      addToast('Episode saved successfully!', 'success');
      queryClient.invalidateQueries({ queryKey: ['episodes'] });
    } catch (error) {
      addToast(`Failed to save episode: ${error}`, 'error');
    }
  };

  // Build service name list from store services dict (Record<string, Service>)
  const servicesMap = services;
  const serviceNames: string[] = Object.keys(servicesMap);

  const getStatusGlow = () => {
    if (episodeDone) return 'border-success/40 bg-success/15 text-success';
    if (episodeTerminated) return 'border-danger/40 bg-danger/15 text-danger';
    if (episodeTruncated) return 'border-warning/40 bg-warning/15 text-warning';
    if (initialized) return 'border-accent/40 bg-accent/15 text-accent';
    return 'border-border bg-bg text-text-secondary';
  };

  return (
    <div className="space-y-6">
      {/* Premium Header */}
      <div className="relative overflow-hidden rounded-2xl bg-surface border border-border p-6">
        <div className="absolute inset-0 bg-accent/10 opacity-5" />
        <div className="absolute -top-8 -right-8 w-40 h-40 rounded-full bg-accent/10" />
        <div className="absolute -bottom-8 -left-8 w-32 h-32 rounded-full bg-accent/10" />
        <div className="relative flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="relative">
                <div className={`w-2.5 h-2.5 rounded-full ${initialized ? 'bg-success animate-pulse' : 'bg-border'}`} />
                {initialized && <div className="absolute inset-0 w-2.5 h-2.5 rounded-full bg-success/50" />}
              </div>
              <span className="text-xs font-medium uppercase tracking-wider text-text-secondary">Incident Response Episode</span>
            </div>
            <h1 className="text-2xl font-bold text-text-primary">
              {initialized ? (
                <span>{taskName || faultType || 'Episode'} — Step {currentStep}</span>
              ) : (
                'Start an Episode'
              )}
            </h1>
            <p className="text-text-secondary text-sm mt-1">
              {initialized
                ? `${actions.length} action${actions.length !== 1 ? 's' : ''} taken · Cumulative reward: ${totalReward.toFixed(3)}`
                : 'Select a fault scenario to begin your incident response training'}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {!initialized ? (
              <button
                onClick={() => handleStartEpisode()}
                disabled={initializing}
                className="group relative px-5 py-2.5 rounded-xl bg-accent/10 text-white font-semibold hover:opacity-90 transition-all disabled:opacity-50 flex items-center gap-2"
              >
                {initializing ? (
                  <>
                    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Initializing...
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Start Episode
                  </>
                )}
              </button>
            ) : (
              <>
                <button
                  onClick={handleSaveEpisode}
                  disabled={episodeDone || actions.length === 0}
                  className="px-4 py-2.5 rounded-xl border border-success/40 bg-success/10 text-success hover:bg-success/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2 font-medium"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                  </svg>
                  Save Episode
                </button>
                <button
                  onClick={() => handleStartEpisode()}
                  disabled={initializing}
                  className="px-4 py-2.5 rounded-xl border border-border bg-surface text-text-secondary hover:text-text-primary hover:border-accent transition-all flex items-center gap-2 font-medium"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Reset
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Status Badges */}
      {(episodeDone || episodeTruncated || episodeTerminated) && (
        <div className="flex flex-wrap gap-3">
          {episodeDone && (
            <span className={`px-4 py-2 rounded-xl border font-semibold text-sm ${getStatusGlow()}`}>
              Episode Complete
            </span>
          )}
          {episodeTruncated && (
            <span className={`px-4 py-2 rounded-xl border font-semibold text-sm ${getStatusGlow()}`}>
              Episode Truncated
            </span>
          )}
          {episodeTerminated && (
            <span className={`px-4 py-2 rounded-xl border font-semibold text-sm ${getStatusGlow()}`}>
              Episode Terminated
            </span>
          )}
        </div>
      )}

      {/* Task Selector (when not initialized) */}
      {!initialized && tasksData?.tasks && tasksData.tasks.length > 0 && (
        <div className="bg-surface border border-border rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-5">
            <div className="p-2 rounded-lg bg-accent/10">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-text-primary">Select a Fault Scenario</h2>
              <p className="text-xs text-text-secondary">Choose a scenario to begin your incident response training</p>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 min-h-[200px]">
            {tasksData.tasks.slice(0, 6).map((task) => {
              const diffColor = Number(task.difficulty) <= 2 ? 'success' : Number(task.difficulty) <= 3 ? 'warning' : 'error';
              return (
                <button
                  key={task.id}
                  onClick={() => handleStartEpisode(task.id)}
                  disabled={initializing}
                  className="group relative overflow-hidden p-4 rounded-xl border border-border bg-surface hover:border-accent hover:bg-surface/80 transition-all disabled:opacity-50 text-left"
                >
                  <div className={`absolute top-0 left-0 w-1 h-full rounded-l-xl bg-${diffColor}`} />
                  <div className="flex items-start gap-3">
                    <div className={`p-2.5 rounded-lg ${diffColor === 'success' ? 'bg-success/15' : diffColor === 'warning' ? 'bg-warning/15' : 'bg-danger/15'}`}>
                      <svg className={`w-5 h-5 ${diffColor === 'success' ? 'text-success' : diffColor === 'warning' ? 'text-warning' : 'text-danger'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-text-primary text-sm">{task.name}</h3>
                      <p className="text-xs text-text-secondary mt-0.5 line-clamp-2">{task.description || task.fault_type}</p>
                      <div className="flex items-center gap-2 mt-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${
                          diffColor === 'success' ? 'bg-success/20 text-success' :
                          diffColor === 'warning' ? 'bg-warning/20 text-warning' :
                          'bg-danger/20 text-danger'
                        }`}>
                          {task.difficulty <= 2 ? 'Easy' : task.difficulty <= 3 ? 'Medium' : 'Hard'}
                        </span>
                        <span className="text-xs text-text-secondary">{task.fault_type}</span>
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Main Content Grid */}
      {initialized && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Action Panel */}
          <div className="lg:col-span-1 space-y-6">
            {/* Action Panel */}
            <div className="bg-surface border border-border rounded-2xl p-6 flex flex-col h-full min-h-[400px]">
              <div className="flex items-center gap-2 mb-4">
                <div className="p-1.5 rounded-lg bg-accent/20">
                  <svg className="w-4 h-4 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-text-primary">Actions</h2>
              </div>
              <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain">
              {actionsData?.actions && actionsData.actions.length > 0 && (
                <ActionPanel
                  actions={actionsData.actions}
                  selectedAction={selectedAction}
                  selectedService={selectedService}
                  services={serviceNames}
                  onActionSelect={setSelectedAction}
                  onServiceSelect={setSelectedService}
                  onExecute={handleExecuteAction}
                  disabled={episodeDone || episodeTruncated || episodeTerminated}
                  loading={executing}
                />
              )}
              </div>
            </div>

            {/* Reward Display */}
            <div className="bg-surface border border-border rounded-2xl p-6 h-full min-h-[200px]">
              <div className="flex items-center gap-2 mb-4">
                <div className="p-1.5 rounded-lg bg-success/20">
                  <svg className="w-4 h-4 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-text-primary">Rewards</h2>
              </div>
              <RewardDisplay
                stepReward={actions.length > 0 ? actions[actions.length - 1].reward : 0}
                cumulativeReward={totalReward}
              />
            </div>
          </div>

          {/* Middle Column - Observation */}
          <div className="lg:col-span-1 h-full min-h-[400px]">
            <div className="bg-surface border border-border rounded-2xl p-6 h-full flex flex-col">
              <div className="flex items-center gap-2 mb-4">
                <div className="p-1.5 rounded-lg bg-accent/20">
                  <svg className="w-4 h-4 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-text-primary">Observation</h2>
              </div>
              <div className="flex-1 min-h-0">
              <ObservationViewer observation={observation} />
              </div>
            </div>
          </div>

          {/* Right Column - Timeline & Services */}
          <div className="lg:col-span-1 space-y-6">
            {/* Timeline */}
            <div className="bg-surface border border-border rounded-2xl p-6 h-full min-h-[300px]">
              <div className="flex items-center gap-2 mb-4">
                <div className="p-1.5 rounded-lg bg-warning/20">
                  <svg className="w-4 h-4 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-text-primary">
                  Timeline ({actions.length})
                </h2>
              </div>
              <div className="flex-1 min-h-0 overflow-y-auto">
              <Timeline entries={actions} currentStep={currentStep} />
              </div>
            </div>

            {/* Services */}
            <div className="bg-surface border border-border rounded-2xl p-6 h-full">
              <div className="flex items-center gap-2 mb-4">
                <div className="p-1.5 rounded-lg bg-danger/20">
                  <svg className="w-4 h-4 text-danger" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-text-primary">Services</h2>
              </div>
              <ServiceGrid
                services={servicesMap}
                selectedService={selectedService}
                onServiceSelect={setSelectedService}
                selectable
              />
            </div>

            {/* Alerts */}
            <div className="bg-surface border border-border rounded-2xl p-6 h-full">
              <div className="flex items-center gap-2 mb-4">
                <div className="p-1.5 rounded-lg bg-yellow-500/20">
                  <svg className="w-4 h-4 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-text-primary">Alerts</h2>
              </div>
              <AlertList alerts={alerts} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
