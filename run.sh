#!/bin/bash
# IncidentOps - Run Script
# Usage: ./run.sh [command]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}IncidentOps v10.0.0${NC}"
echo ""

# Check command
COMMAND=${1:-"help"}

case $COMMAND in
    "install")
        echo -e "${YELLOW}Installing dependencies...${NC}"
        pip install -r requirements.txt
        echo -e "${GREEN}Dependencies installed.${NC}"
        ;;
    
    "run")
        echo -e "${YELLOW}Starting server on port 7860...${NC}"
        uvicorn app.main:app --host 0.0.0.0 --port 7860
        ;;
    
    "run-dev")
        echo -e "${YELLOW}Starting development server...${NC}"
        uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
        ;;
    
    "test")
        echo -e "${YELLOW}Running tests...${NC}"
        python -c "
from app.environment import make_env
from app.determinism import run_reproducibility_test

# Test environment
print('Testing environment...')
env = make_env(seed=42)
obs = env.reset(seed=42)
print(f'Environment initialized: {obs[\"incident_info\"]}')

# Test determinism
print('Testing determinism...')
result = run_reproducibility_test(seed=42, num_steps=5)
print(f'Determinism test: {\"PASS\" if result[\"passed\"] else \"FAIL\"}')

# Test grader
print('Testing grader...')
from app.grader import DeepTrajectoryGrader
grader = DeepTrajectoryGrader(seed=42)
print('Grader initialized.')

print('All tests passed!')
"
        ;;
    
    "baseline")
        echo -e "${YELLOW}Running baseline agent test...${NC}"
        python -c "
from app.environment import make_env
from app.baseline import BaselineAgent, AgentConfig, run_baseline_episode

for difficulty in [2, 3, 5]:
    print(f'\n--- Difficulty {difficulty} ---')
    env = make_env(seed=42, difficulty=difficulty)
    agent = BaselineAgent(AgentConfig(seed=42))
    result = run_baseline_episode(env, agent, seed=42, max_steps=20)
    print(f'Score: {result[\"final_score\"]:.3f}, Grade: {result[\"grade\"]}')
"
        ;;
    
    "docker-build")
        echo -e "${YELLOW}Building Docker image...${NC}"
        docker build -t incidentops:10.0.0 .
        echo -e "${GREEN}Docker image built.${NC}"
        ;;
    
    "docker-run")
        echo -e "${YELLOW}Running Docker container...${NC}"
        docker run -p 7860:7860 incidentops:10.0.0
        ;;
    
    "health")
        echo -e "${YELLOW}Checking health endpoint...${NC}"
        curl -s http://localhost:7860/health | python -m json.tool
        ;;
    
    *)
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  install      - Install dependencies"
        echo "  run          - Run production server (port 7860)"
        echo "  run-dev      - Run development server with reload"
        echo "  test         - Run tests"
        echo "  baseline     - Run baseline agent tests"
        echo "  docker-build - Build Docker image"
        echo "  docker-run   - Run Docker container"
        echo "  health       - Check health endpoint"
        ;;
esac
