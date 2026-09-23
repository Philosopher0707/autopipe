"""Pipeline orchestration."""

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .execution import ExecutionContext, ExecutionEngine, NullEventSink
from .step import Step

logger = logging.getLogger(__name__)


class Pipeline:
    """Manages a DAG of steps and executes them."""

    def __init__(self, name: str):
        self.name = name
        self.steps: Dict[str, Step] = {}
        self._execution_order: List[Step] = []
        #: Declared run seed (set by the loader from config); passed to the
        #: engine as ExecutionContext.seed so run-local RNG is applied.
        self.seed: Optional[int] = None

    def add_step(self, step: Step) -> "Pipeline":
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
        graph: Dict[str, List[str]] = {name: [] for name in self.steps}

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

        Delegates to the canonical engine
        (:class:`~autopipe.core.execution.ExecutionEngine`) so that the library,
        the CLI, the dashboard and future workers all share one execution
        semantic (invariants I1/I4). This method used to contain a second,
        hand-written execution loop.

        The historical contract is preserved exactly: the first step exception is
        re-raised unchanged, ``step.output`` is assigned per step, and the return
        value is the step-name-keyed output mapping. Callers that want a
        structured outcome instead of an exception should use the engine directly.

        Args:
            initial_inputs: Optional dictionary of inputs for steps that have no dependencies.

        Returns:
            Dictionary of step outputs keyed by step name.

        Raises:
            Exception: whatever the failing step (or an invalid dependency graph)
                raised, unchanged.
        """
        logger.info("Running pipeline %s", self.name)
        engine = ExecutionEngine()
        context = ExecutionContext(
            run_id=uuid4().hex,
            pipeline_name=self.name,
            initial_inputs=initial_inputs,
            seed=self.seed,
            sink=NullEventSink(),
        )
        result = engine.execute(self, context)
        if result.exception is not None:
            raise result.exception
        return result.outputs

    def visualize_all(self) -> None:
        """Generate visualizations for all steps."""
        for step in self.steps.values():
            try:
                step.visualize()
            except Exception as e:
                logger.warning(f"Visualization failed for step {step.name}: {e}")
