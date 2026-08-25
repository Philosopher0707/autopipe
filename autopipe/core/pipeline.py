"""Pipeline orchestration."""

import logging
from typing import Any, Dict, List, Optional

from .step import Step

logger = logging.getLogger(__name__)


class Pipeline:
    """Manages a DAG of steps and executes them."""

    def __init__(self, name: str):
        self.name = name
        self.steps: Dict[str, Step] = {}
        self._execution_order: List[Step] = []

    def add_step(self, step: Step):
        """Add a step to the pipeline."""
        if step.name in self.steps:
            raise ValueError(f"Step with name {step.name} already exists")
        self.steps[step.name] = step
        return self

    def get_step(self, name: str) -> Step:
        """Get a step by name."""
        if name not in self.steps:
            raise KeyError(f"Step '{name}' not found in pipeline")
        return self.steps[name]

    @property
    def execution_order(self) -> List[str]:
        """Get the execution order (list of step names)."""
        self._execution_order = self._topological_sort()
        return [step.name for step in self._execution_order]

    def _topological_sort(self) -> List[Step]:
        """Determine execution order based on dependencies."""
        # Kahn's algorithm
        in_degree = dict.fromkeys(self.steps, 0)
        graph = {name: [] for name in self.steps}

        for step in self.steps.values():
            for dep in step.depends_on:
                if dep not in self.steps:
                    raise ValueError(f"Dependency {dep} not found in pipeline")
                graph[dep].append(step.name)
                in_degree[step.name] += 1

        # queue of nodes with no incoming edges
        queue = [name for name, deg in in_degree.items() if deg == 0]
        order = []

        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.steps):
            raise ValueError("Pipeline has a cycle, cannot sort")

        return [self.steps[name] for name in order]

    def run(self, initial_inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the pipeline.

        Args:
            initial_inputs: Optional dictionary of inputs for steps that have no dependencies.

        Returns:
            Dictionary of step outputs keyed by step name.
        """
        logger.info("Running pipeline %s", self.name)
        self._execution_order = self._topological_sort()

        outputs: Dict[str, Any] = dict(initial_inputs or {})

        for step in self._execution_order:
            # Gather outputs of declared dependencies as inputs
            if step.depends_on:
                inputs = {dep: outputs[dep] for dep in step.depends_on if dep in outputs}
            else:
                inputs = dict(initial_inputs or {})

            logger.info("Running step %s", step.name)
            try:
                step_output = step.run(**inputs)
                outputs[step.name] = step_output
                # Persist on the step itself so visualize() and introspection
                # can access this step's result (was never assigned before).
                step.output = step_output
            except Exception:
                logger.error("Step %s failed", step.name)
                raise

            # Generate visualizations
            try:
                step.visualize(**inputs)
            except Exception as e:
                logger.warning("Visualization failed for step %s: %s", step.name, e)

        logger.info("Pipeline %s completed", self.name)
        return outputs

    def visualize_all(self):
        """Generate visualizations for all steps."""
        for step in self.steps.values():
            try:
                step.visualize()
            except Exception as e:
                logger.warning(f"Visualization failed for step {step.name}: {e}")
