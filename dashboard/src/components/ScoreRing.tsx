interface ScoreRingProps {
  score: number;
  maxScore?: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
}

export function ScoreRing({ score, maxScore = 1, size = 120, strokeWidth = 8, label }: ScoreRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const percentage = Math.min(Math.max((score / maxScore) * 100, 0), 100);
  const offset = circumference - (percentage / 100) * circumference;

  const getColor = () => {
    if (percentage >= 80) return '#22c55e';
    if (percentage >= 60) return '#eab308';
    if (percentage >= 40) return '#f97316';
    return '#ef4444';
  };

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg className="transform -rotate-90" width={size} height={size}>
          <circle
            className="text-border"
            strokeWidth={strokeWidth}
            stroke="currentColor"
            fill="transparent"
            r={radius}
            cx={size / 2}
            cy={size / 2}
          />
          <circle
            className="transition-all duration-500 ease-out"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            stroke={getColor()}
            fill="transparent"
            r={radius}
            cx={size / 2}
            cy={size / 2}
            style={{
              strokeDasharray: circumference,
              strokeDashoffset: offset,
            }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold text-text-primary">{score.toFixed(2)}</span>
          <span className="text-xs text-text-secondary">/ {maxScore.toFixed(0)}</span>
        </div>
      </div>
      {label && <span className="text-sm text-text-secondary">{label}</span>}
    </div>
  );
}
