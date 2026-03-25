"""Job shop scheduling evaluator with 5 benchmark instances."""
import importlib.util
import random
import sys
import os


def generate_instance(seed, n_jobs, n_machines, n_ops_range, time_range,
                      slack_factor=1.5):
    """Generate a deterministic job shop instance."""
    rng = random.Random(seed)
    jobs = []
    for j in range(n_jobs):
        n_ops = rng.randint(*n_ops_range)
        ops = []
        total_time = 0
        for _ in range(n_ops):
            # Each op can run on 1-3 eligible machines
            n_eligible = rng.randint(1, min(3, n_machines))
            eligible = sorted(rng.sample(range(n_machines), n_eligible))
            duration = {}
            for m in eligible:
                duration[m] = rng.randint(*time_range)
            ops.append({"eligible": eligible, "duration": duration})
            total_time += min(duration.values())

        release = rng.randint(0, total_time // 2)
        due = release + int(total_time * slack_factor * rng.uniform(0.8, 1.5))
        weight = round(rng.uniform(0.5, 5.0), 1)

        jobs.append({
            "id": j,
            "release": release,
            "due": due,
            "weight": weight,
            "ops": ops,
        })
    return jobs, n_machines


INSTANCES = [
    # (seed, n_jobs, n_machines, n_ops_range, time_range, slack_factor)
    (100, 10, 3, (2, 4), (5, 20), 1.8),    # Easy
    (200, 15, 4, (2, 5), (5, 25), 1.5),    # Medium
    (300, 25, 5, (3, 6), (5, 30), 1.3),    # Hard
    (400, 35, 6, (3, 7), (8, 35), 1.2),    # Very hard
    (500, 50, 8, (3, 8), (5, 40), 1.0),    # Extreme
]


def validate_schedule(schedule, jobs, n_machines):
    """Validate schedule and return weighted tardiness, or None if invalid."""
    job_map = {j["id"]: j for j in jobs}

    # Check all operations are scheduled
    expected_ops = set()
    for j in jobs:
        for op_idx in range(len(j["ops"])):
            expected_ops.add((j["id"], op_idx))

    scheduled_ops = set()
    for job_id, op_idx, machine, start in schedule:
        scheduled_ops.add((job_id, op_idx))

    if expected_ops != scheduled_ops:
        return None  # Missing or extra operations

    # Build schedule by machine
    machine_schedule = [[] for _ in range(n_machines)]
    job_op_schedule = {}  # (job_id, op_idx) -> (machine, start, end)

    for job_id, op_idx, machine, start in schedule:
        job = job_map[job_id]
        op = job["ops"][op_idx]

        # Check machine eligibility
        if machine not in op["eligible"]:
            return None

        duration = op["duration"][machine]
        end = start + duration
        job_op_schedule[(job_id, op_idx)] = (machine, start, end)
        machine_schedule[machine].append((start, end, job_id, op_idx))

    # Check no machine overlaps
    for m in range(n_machines):
        slots = sorted(machine_schedule[m])
        for i in range(len(slots) - 1):
            if slots[i][1] > slots[i + 1][0]:
                return None  # Overlap

    # Check precedence (ops within job are sequential)
    for j in jobs:
        for op_idx in range(1, len(j["ops"])):
            prev = job_op_schedule.get((j["id"], op_idx - 1))
            curr = job_op_schedule.get((j["id"], op_idx))
            if prev is None or curr is None:
                return None
            if curr[1] < prev[2]:  # start < prev_end
                return None

    # Check release times
    for j in jobs:
        first_op = job_op_schedule.get((j["id"], 0))
        if first_op is None:
            return None
        if first_op[1] < j["release"]:
            return None

    # Compute weighted tardiness
    total_tardiness = 0.0
    for j in jobs:
        last_op = job_op_schedule[(j["id"], len(j["ops"]) - 1)]
        completion = last_op[2]
        tardiness = max(0, completion - j["due"])
        total_tardiness += j["weight"] * tardiness

    return total_tardiness


def load_scheduler():
    spec = importlib.util.spec_from_file_location("scheduler", "target/scheduler.py")
    mod = importlib.util.module_from_spec(spec)
    # Load helpers so scheduler can import them
    for name, path in [("heuristics", "target/heuristics.py"),
                       ("config", "target/config.py")]:
        s = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(s)
        sys.modules[name] = m
        s.loader.exec_module(m)
    spec.loader.exec_module(mod)
    return mod.schedule


def evaluate():
    try:
        schedule_fn = load_scheduler()
    except Exception as e:
        print(f"SCORE: 500000", flush=True)
        return

    total_score = 0.0
    penalty = 100000

    for inst_args in INSTANCES:
        jobs, n_machines = generate_instance(*inst_args)
        try:
            result = schedule_fn(jobs, n_machines)
            tardiness = validate_schedule(result, jobs, n_machines)
            if tardiness is None:
                total_score += penalty
            else:
                total_score += tardiness
        except Exception as e:
            total_score += penalty

    print(f"SCORE: {total_score:.2f}", flush=True)


if __name__ == "__main__":
    evaluate()
