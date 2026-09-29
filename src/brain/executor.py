from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed


class ParallelActionExecutor:
    """Run only independent, non-mutating Nexus actions in parallel."""

    SAFE_PARALLEL_TOOLS = frozenset({"web_search", "read_page", "calculator"})
    MAX_WORKERS = 3

    def can_parallelize(self, task: dict) -> bool:
        return (
            isinstance(task, dict)
            and task.get("tool") in self.SAFE_PARALLEL_TOOLS
            and isinstance(task.get("args"), dict)
        )

    def run(self, tasks: list[dict], execute) -> list[tuple[int, dict]]:
        """Return (original_index, result) pairs in original task order."""
        if len(tasks) <= 1:
            return [(0, execute(tasks[0]))] if tasks else []

        results: dict[int, dict] = {}
        with ThreadPoolExecutor(max_workers=min(self.MAX_WORKERS, len(tasks))) as pool:
            futures = {
                pool.submit(execute, task): index
                for index, task in enumerate(tasks)
            }
            for future in as_completed(futures):
                index = futures[future]
                try:
                    results[index] = future.result()
                except Exception as exc:
                    results[index] = {
                        "verified": False,
                        "error": f"Parallel execution failed: {type(exc).__name__}",
                        "result": {},
                    }

        return [(index, results[index]) for index in sorted(results)]
