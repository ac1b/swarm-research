"""Dispatching rules and local search operators for scheduling."""


def priority_score(job, op, current_time):
    """Compute priority for dispatching. Higher = scheduled first."""
    # Simple FIFO by release time
    return -job["release"]


def local_search_swap(schedule, jobs, n_machines):
    """Try to improve schedule by swapping operations. Returns improved schedule or None."""
    return None


def local_search_insert(schedule, jobs, n_machines):
    """Try to improve by reinserting an operation. Returns improved schedule or None."""
    return None
