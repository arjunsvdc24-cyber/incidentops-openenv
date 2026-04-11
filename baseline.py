#!/usr/bin/env python3
"""
IncidentOps Baseline Runner

Produces reproducible baseline scores for all three tasks.
Can run with or without OpenAI API key.

Usage:
    python baseline.py                    # Run all tasks
    python baseline.py --task easy        # Run specific task
    python baseline.py --server           # Also start server

Requirements:
    - Running server at OPENENV_BASE_URL (default: http://localhost:7860)
    - Optional: OPENAI_API_KEY for LLM-powered baseline
"""

import argparse
import os
import sys
import json

# Default base URL for the OpenEnv server
OPENENV_BASE_URL = os.environ.get("OPENENV_BASE_URL", "http://localhost:7860")


def run_rule_based_baseline(task_id: str = None) -> dict:
    """
    Run the rule-based baseline via the /baseline endpoint.
    
    Args:
        task_id: Optional specific task to run. If None, runs all tasks.
    
    Returns:
        Dictionary with baseline scores.
    """
    import requests
    
    try:
        if task_id:
            # Run specific task - use /reset, /step, /grader
            resp = requests.post(f"{OPENENV_BASE_URL}/reset", json={
                "task_id": task_id,
                "seed": 42
            })
            if resp.status_code != 200:
                raise Exception(f"Reset failed: {resp.text}")
            
            # Run the rule-based actions for this task
            # The server has built-in baseline logic
            resp = requests.post(f"{OPENENV_BASE_URL}/baseline")
            data = resp.json()
            
            return {task_id: data[task_id]}
        else:
            # Run full baseline
            resp = requests.post(f"{OPENENV_BASE_URL}/baseline")
            return resp.json()
            
    except requests.exceptions.ConnectionError:
        raise Exception(f"Could not connect to server at {OPENENV_BASE_URL}")


def run_llm_baseline(task_id: str = None) -> dict:
    """
    Run the LLM-powered baseline using OpenAI API.

    Args:
        task_id: Optional specific task to run.

    Returns:
        Dictionary with baseline scores.
    """
    from openai import OpenAI

    # HACKATHON: Use injected API_BASE_URL + API_KEY first
    api_key = os.environ.get("API_KEY")
    base_url = os.environ.get("API_BASE_URL")
    if not api_key or not base_url:
        # Fall back to standard env var
        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = None  # Use default OpenAI endpoint

    client = OpenAI(api_key=api_key, base_url=base_url) if api_key else None

    # Import the LLM baseline agent
    from app.llm_baseline import run_llm_evaluation

    results = run_llm_evaluation(seed=42, verbose=True, api_key=api_key, base_url=base_url)

    if task_id:
        return {task_id: results[task_id]}
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Run IncidentOps baseline evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python baseline.py                    # Run all tasks (rule-based)
    python baseline.py --task easy        # Run specific task
    python baseline.py --llm              # Use LLM baseline (requires OPENAI_API_KEY)
    python baseline.py --server           # Start server automatically
        """
    )
    parser.add_argument(
        "--task", 
        choices=["easy", "medium", "hard"],
        help="Run specific task only"
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Use LLM-powered baseline (requires OPENAI_API_KEY)"
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="Start the server automatically if not running"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Port for the server (default: 7860)"
    )
    
    args = parser.parse_args()
    
    # Check for OpenAI API key if using LLM mode
    # HACKATHON: Check injected vars first
    api_key = os.environ.get("API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("WARNING: OPENAI_API_KEY not set. Running rule-based baseline via /baseline endpoint.")
        import requests
        try:
            resp = requests.post(f"{OPENENV_BASE_URL}/baseline")
            data = resp.json()
            print(f"\nRule-based baseline results:")
            print(f"  Easy:   {data['easy']:.3f}")
            print(f"  Medium: {data['medium']:.3f}")
            print(f"  Hard:   {data['hard']:.3f}")
            print(f"  Mean:   {data['total']:.3f}")
        except Exception as e:
            print(f"Could not reach API at {OPENENV_BASE_URL}: {e}")
            print("Start the server first: uvicorn app.main:app --host 0.0.0.0 --port 7860")
            sys.exit(1)
        sys.exit(0)
    
    # Start server if requested
    if args.server:
        import subprocess
        import time
        import requests
        
        # Check if server is already running
        try:
            resp = requests.get(f"{OPENENV_BASE_URL}/health")
            print(f"Server already running at {OPENENV_BASE_URL}")
        except:
            print(f"Starting server on port {args.port}...")
            proc = subprocess.Popen(
                ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(args.port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            # Wait for server to start
            for _ in range(30):
                try:
                    resp = requests.get(f"{OPENENV_BASE_URL}/health")
                    print("Server started successfully")
                    break
                except:
                    time.sleep(0.5)
    
    # Run baseline
    try:
        if args.llm:
            print("Running LLM-powered baseline...")
            results = run_llm_baseline(args.task)
        else:
            print("Running rule-based baseline...")
            results = run_rule_based_baseline(args.task)
        
        print("\n" + "="*50)
        print("BASELINE RESULTS")
        print("="*50)
        
        if "easy" in results:
            for task in ["easy", "medium", "hard"]:
                if task in results:
                    score = results[task]
                    if isinstance(score, (int, float)):
                        print(f"  {task.capitalize()}: {score:.3f}")
            if "total" in results:
                print(f"\n  Mean: {results['total']:.3f}")
        else:
            for task, score in results.items():
                if isinstance(score, (int, float)):
                    print(f"  {task.capitalize()}: {score:.3f}")
        
        print("="*50)
        
    except Exception as e:
        print(f"Error: {e}")
        print(f"\nMake sure the server is running at {OPENENV_BASE_URL}")
        print("Start with: uvicorn app.main:app --host 0.0.0.0 --port 7860")
        sys.exit(1)


if __name__ == "__main__":
    main()
