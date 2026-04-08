import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getEpisode } from '../api/client';
import { ObservationViewer } from '../components/ObservationViewer';
import { ScoreRing } from '../components/ScoreRing';
import { format } from 'date-fns';

export function ReplayPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [showAll, setShowAll] = useState(false);

  const { data: episode, isLoading, error } = useQuery({
    queryKey: ['episode', id],
    queryFn: () => getEpisode(id!),
    enabled: !!id,
  });

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <svg className="w-16 h-16 text-danger mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <h2 className="text-xl font-semibold text-text-primary mb-2">Episode Not Found</h2>
        <p className="text-text-secondary mb-4">The requested episode could not be found</p>
        <button
          onClick={() => navigate('/episodes')}
          className="px-4 py-2 rounded-lg border border-border text-text-secondary hover:text-text-primary hover:border-accent transition-colors"
        >
          Back to Episodes
        </button>
      </div>
    );
  }

  if (isLoading || !episode) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-center py-12">
          <svg className="animate-spin w-8 h-8 text-accent" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
      </div>
    );
  }

  const currentEntry = showAll ? episode.trajectory[episode.trajectory.length - 1] : episode.trajectory[currentStep];
  const totalSteps = episode.trajectory.length;

  const handleNextStep = () => {
    if (showAll) {
      setShowAll(false);
      setCurrentStep(0);
    } else if (currentStep < totalSteps - 1) {
      setCurrentStep((s) => s + 1);
    } else {
      setShowAll(true);
    }
  };

  const handlePrevStep = () => {
    if (showAll) {
      setShowAll(false);
      setCurrentStep(totalSteps - 1);
    } else if (currentStep > 0) {
      setCurrentStep((s) => s - 1);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <button
            onClick={() => navigate('/episodes')}
            className="flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors mb-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Episodes
          </button>
          <h1 className="text-2xl font-bold text-text-primary">
            Episode Replay
          </h1>
          <p className="text-text-secondary text-sm mt-1">
            {episode.fault_type} - {episode.task_name}
          </p>
        </div>
        <ScoreRing score={episode.grade * 100} maxScore={100} size={80} strokeWidth={6} label="Grade" />
      </div>

      {/* Episode Info */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-text-secondary uppercase tracking-wider">Fault Type</p>
            <p className="text-sm font-medium text-text-primary mt-1">{episode.fault_type}</p>
          </div>
          <div>
            <p className="text-xs text-text-secondary uppercase tracking-wider">Steps</p>
            <p className="text-sm font-medium text-text-primary mt-1">{episode.steps}</p>
          </div>
          <div>
            <p className="text-xs text-text-secondary uppercase tracking-wider">Score</p>
            <p className="text-sm font-medium text-success font-mono mt-1">
              {episode.score.toFixed(3)}
            </p>
          </div>
          <div>
            <p className="text-xs text-text-secondary uppercase tracking-wider">Date</p>
            <p className="text-sm font-medium text-text-primary mt-1">
              {format(new Date(episode.created_at), 'MMM d, yyyy')}
            </p>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="bg-surface border border-border rounded-xl p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-text-secondary">
            {showAll ? 'Complete Replay' : `Step ${currentStep + 1} of ${totalSteps}`}
          </span>
          <span className="text-sm text-text-secondary">
            {totalSteps} total actions
          </span>
        </div>
        <div className="h-2 bg-bg rounded-full overflow-hidden">
          <div
            className="h-full bg-accent/10 transition-all duration-300"
            style={{ width: `${((showAll ? totalSteps : currentStep + 1) / totalSteps) * 100}%` }}
          />
        </div>
        <div className="flex gap-1 mt-2">
          {episode.trajectory.map((_, index) => (
            <button
              key={index}
              onClick={() => {
                setShowAll(false);
                setCurrentStep(index);
              }}
              className={`flex-1 h-1 rounded transition-colors ${
                showAll || index > currentStep
                  ? 'bg-border'
                  : index === currentStep
                  ? 'bg-accent'
                  : 'bg-success'
              }`}
            />
          ))}
        </div>
      </div>

      {/* Replay Controls */}
      <div className="flex items-center justify-center gap-4">
        <button
          onClick={() => {
            setShowAll(false);
            setCurrentStep(0);
          }}
          disabled={currentStep === 0 && !showAll}
          className="p-2 rounded-lg border border-border text-text-secondary hover:text-text-primary hover:border-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          title="Go to start"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
        <button
          onClick={handlePrevStep}
          disabled={currentStep === 0 && !showAll}
          className="p-2 rounded-lg border border-border text-text-secondary hover:text-text-primary hover:border-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          title="Previous step"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <button
          onClick={handleNextStep}
          className="px-6 py-2 rounded-lg bg-accent/10 text-white font-medium hover:opacity-90 transition-opacity flex items-center gap-2"
        >
          {showAll ? (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Replay
            </>
          ) : currentStep === totalSteps - 1 ? (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Complete
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
              Next Step
            </>
          )}
        </button>
      </div>

      {/* Current State Display */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Current Action */}
        <div className="bg-surface border border-border rounded-xl p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Current Action</h2>
          {currentEntry ? (
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="flex items-center justify-center w-12 h-12 rounded-full bg-accent/10 text-white font-bold text-lg">
                  {currentEntry.step}
                </div>
                <div>
                  <p className="text-lg font-medium text-text-primary">
                    {currentEntry.action_type?.replace('_', ' ') ?? currentEntry.action_type}
                  </p>
                  {currentEntry.target_service && (
                    <p className="text-sm text-text-secondary">
                      Target: {currentEntry.target_service}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex gap-4">
                <div className="flex-1 p-3 rounded-lg bg-bg">
                  <p className="text-xs text-text-secondary uppercase tracking-wider">Step Reward</p>
                  <p className={`text-xl font-mono font-bold ${
                    currentEntry.reward > 0 ? 'text-success' :
                    currentEntry.reward < 0 ? 'text-danger' : 'text-text-secondary'
                  }`}>
                    {currentEntry.reward > 0 ? '+' : ''}{currentEntry.reward.toFixed(3)}
                  </p>
                </div>
                <div className="flex-1 p-3 rounded-lg bg-bg">
                  <p className="text-xs text-text-secondary uppercase tracking-wider">Cumulative</p>
                  <p className="text-xl font-mono font-bold text-text-primary">
                    {currentEntry.cumulative_reward.toFixed(3)}
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-text-secondary">No action at this step</p>
          )}
        </div>

        {/* Observation */}
        <div className="bg-surface border border-border rounded-xl p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Observation</h2>
          <ObservationViewer observation={currentEntry?.observation || null} />
        </div>
      </div>

      {/* Action Timeline */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">Action Timeline</h2>
        <div className="flex flex-wrap gap-2">
          {episode.trajectory.map((entry, index) => (
            <button
              key={index}
              onClick={() => {
                setShowAll(false);
                setCurrentStep(index);
              }}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-all ${
                showAll
                  ? 'border-success/30 bg-success/10'
                  : index === currentStep
                  ? 'border-accent bg-accent/10'
                  : 'border-border hover:border-accent/50'
              }`}
            >
              <span className={`text-xs font-bold ${
                showAll
                  ? 'text-success'
                  : index === currentStep
                  ? 'text-accent'
                  : 'text-text-secondary'
              }`}>
                {entry.step}
              </span>
              <span className="text-xs text-text-primary">
                {entry.action_type?.replace('_', ' ') ?? entry.action_type}
              </span>
              <span className={`text-xs font-mono ${
                entry.reward > 0 ? 'text-success' :
                entry.reward < 0 ? 'text-danger' : 'text-text-secondary'
              }`}>
                {entry.reward > 0 ? '+' : ''}{entry.reward.toFixed(1)}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
