interface RewardDisplayProps {
  stepReward: number;
  cumulativeReward: number;
}

export function RewardDisplay({ stepReward, cumulativeReward }: RewardDisplayProps) {
  const getRewardColor = (reward: number) => {
    if (reward > 0) return 'text-success';
    if (reward < 0) return 'text-danger';
    return 'text-text-secondary';
  };

  const getRewardSign = (reward: number) => {
    if (reward > 0) return '+';
    return '';
  };

  return (
    <div className="flex items-center gap-6">
      <div className="flex flex-col items-center">
        <span className="text-xs text-text-secondary uppercase tracking-wider">Step Reward</span>
        <span className={`text-xl font-mono font-bold ${getRewardColor(stepReward)}`}>
          {getRewardSign(stepReward)}
          {stepReward.toFixed(3)}
        </span>
      </div>
      <div className="h-10 w-px bg-border" />
      <div className="flex flex-col items-center">
        <span className="text-xs text-text-secondary uppercase tracking-wider">Cumulative</span>
        <span className={`text-xl font-mono font-bold ${getRewardColor(cumulativeReward)}`}>
          {getRewardSign(cumulativeReward)}
          {cumulativeReward.toFixed(3)}
        </span>
      </div>
    </div>
  );
}
