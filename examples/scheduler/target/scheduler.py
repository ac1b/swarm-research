"""Job shop scheduler. Optimize to minimize weighted tardiness."""


def schedule(jobs, n_machines):
    """Schedule jobs on machines to minimize weighted tardiness.

    Args:
        jobs: list of dicts with keys: id, release, due, weight, ops
              ops: list of dicts with keys: eligible (list of machine ids),
                   duration (dict {machine_id: time})
        n_machines: number of machines

    Returns:
        list of (job_id, op_index, machine, start_time) tuples
    """
    result = []
    machine_avail = [0] * n_machines

    # FIFO: process jobs in order, assign each op to first available eligible machine
    for job in sorted(jobs, key=lambda j: j["release"]):
        job_time = job["release"]
        for op_idx, op in enumerate(job["ops"]):
            # Pick eligible machine with earliest availability
            best_machine = op["eligible"][0]
            best_start = max(job_time, machine_avail[best_machine])
            for m in op["eligible"]:
                start = max(job_time, machine_avail[m])
                if start < best_start:
                    best_start = start
                    best_machine = m

            duration = op["duration"][best_machine]
            result.append((job["id"], op_idx, best_machine, best_start))
            machine_avail[best_machine] = best_start + duration
            job_time = best_start + duration  # next op can't start until this finishes

    return result
