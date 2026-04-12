#!/usr/bin/env python3
"""
Load test — simulate concurrent episode runs
"""
import asyncio
import httpx
import time
import random
from typing import List


BASE = "http://localhost:7860"


async def run_episode(client: httpx.AsyncClient, seed: int, fault_type: str) -> dict:
    """Run a single episode"""
    start = time.time()

    # Reset
    reset_r = await client.post(
        f"{BASE}/reset",
        json={"seed": seed, "fault_type": fault_type, "difficulty": random.choice([2, 3, 5])},
        timeout=30,
    )
    reset_r.raise_for_status()
    obs = reset_r.json()

    steps = 0
    total_reward = 0.0

    # Run a few steps
    actions = [
        ("query_service", "api-gateway"),
        ("query_metrics", "payment-service"),
        ("query_logs", "auth-service"),
        ("restart_service", "payment-service"),
    ]

    for action_type, service in actions:
        try:
            step_r = await client.post(
                f"{BASE}/step",
                json={"action_type": action_type, "target_service": service},
                timeout=30,
            )
            step_r.raise_for_status()
            data = step_r.json()
            total_reward += data.get("reward", 0)
            steps += 1
            if data.get("terminated"):
                break
        except Exception:
            break

    duration = time.time() - start

    # Save episode
    try:
        save_r = await client.post(
            f"{BASE}/episodes",
            json={
                "episode_id": f"load_test_{seed}_{fault_type}",
                "fault_type": fault_type,
                "difficulty": 3,
                "seed": seed,
                "agent_type": "load_test",
                "actions": [{"action_type": a[0], "target_service": a[1]} for a in actions[:steps]],
                "observations": [obs],
                "rewards": [],
                "total_reward": total_reward,
                "final_score": round(total_reward / max(steps, 1), 3),
                "grade": "good",
                "num_steps": steps,
            },
            timeout=30,
        )
        save_r.raise_for_status()
    except Exception:
        pass

    return {
        "seed": seed,
        "fault_type": fault_type,
        "steps": steps,
        "reward": round(total_reward, 3),
        "duration_ms": round(duration * 1000),
    }


async def run_load_test(concurrent: int = 10, total: int = 50):
    """Run concurrent load test"""
    print(f"Starting load test: {total} episodes, {concurrent} concurrent")

    fault_types = ["oom", "cascade", "ghost"]
    tasks: List[asyncio.Task] = []

    async with httpx.AsyncClient() as client:
        # Check server is up
        try:
            r = await client.get(f"{BASE}/health", timeout=10)
            r.raise_for_status()
            print(f"Server healthy: {r.json()}")
        except Exception as e:
            print(f"Server not reachable: {e}")
            return

        start = time.time()

        for i in range(total):
            seed = random.randint(1, 999999)
            fault = random.choice(fault_types)
            task = asyncio.create_task(run_episode(client, seed, fault))
            tasks.append(task)

            # Limit concurrency
            if len(tasks) >= concurrent:
                results = await asyncio.gather(*tasks)
                for r in results:
                    print(f"  seed={r['seed']} fault={r['fault_type']} steps={r['steps']} reward={r['reward']} {r['duration_ms']}ms")
                tasks = []

        # Remaining tasks
        if tasks:
            results = await asyncio.gather(*tasks)
            for r in results:
                print(f"  seed={r['seed']} fault={r['fault_type']} steps={r['steps']} reward={r['reward']} {r['duration_ms']}ms")

    elapsed = time.time() - start
    print(f"\nLoad test complete: {total} episodes in {elapsed:.2f}s")
    print(f"Throughput: {total / elapsed:.1f} episodes/sec")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrent", type=int, default=10)
    parser.add_argument("--total", type=int, default=50)
    args = parser.parse_args()

    asyncio.run(run_load_test(concurrent=args.concurrent, total=args.total))
