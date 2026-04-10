"""Debug script for baseline cascade scoring"""
import sys
sys.path.insert(0, '.')

from app.environment import make_env
from app.fault_injector import FaultType
from app.baseline import BaselineAgent, AgentConfig, AgentStrategy
from app.enhanced_grader import grade_trajectory_enhanced

seed = 42

for name, diff, fault in [('cascade', 3, FaultType.CASCADE), ('easy', 2, FaultType.OOM), ('hard', 5, FaultType.GHOST)]:
    print(f'\n{"="*60}')
    print(f'{name.upper()} (difficulty={diff})')
    print(f'{"="*60}')
    env = make_env(seed=seed, difficulty=diff, fault_type=fault)
    obs = env.reset(seed=seed)
    rc = env.current_scenario.root_cause_service
    cf = env.current_scenario.correct_fix
    af = env.current_scenario.affected_services
    print(f'Root cause: {rc}')
    print(f'Correct fix: {cf}')

    agent = BaselineAgent(AgentConfig(seed=seed, strategy=AgentStrategy.SYSTEMATIC))
    agent.reset(seed)

    actions_log = []
    for step in range(20):
        action = agent.act(obs)
        actions_log.append({'action_type': action['action_type'], 'target_service': action.get('target_service')})
        response = env.step(action)
        obs = response.observation
        if response.terminated or response.truncated:
            break

    scenario_data = {
        'fault_type': fault.value,
        'difficulty': diff,
        'root_cause_service': rc,
        'affected_services': af,
        'correct_fix': cf,
    }
    trajectory = {
        'actions': actions_log,
        'rewards': [],
        'final_state': {'fix_applied': env.fix_applied},
        'scenario': scenario_data,
    }
    evaluation = grade_trajectory_enhanced(trajectory, scenario_data, seed=seed)
    print(f'Score: {evaluation.breakdown.final_score:.3f}')
    print(f'  rc={evaluation.breakdown.root_cause_score:.2f} fix={evaluation.breakdown.fix_score:.2f} eff={evaluation.breakdown.efficiency_score:.2f} disr={evaluation.breakdown.disruption_score:.2f} reason={evaluation.breakdown.reasoning_score:.2f}')
    print(f'Fix applied: {env.fix_applied}, ID root cause: {agent.identified_root_cause}')
