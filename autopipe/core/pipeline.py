"""Pipeline orchestration."""
import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .step import Step

if TYPE_CHECKING:
    from autopipe.dashboard.state import PipelineState

logger = logging.getLogger(__name__)

PipelineWatcher = Callable[["PipelineState", str, Any], None]


class Pipeline:
    """Manages a DAG of steps and executes them."""

    def __init__(self, name: str):
        self.name = name
        self.steps: Dict[str, Step] = {}
        self._execution_order: List[Step] = []
        self._watchers: List[Callable] = []

    def add_step(self, step: Step):
        """Add a step to the pipeline."""
        if step.name in self.steps:
            raise ValueError(f"Step with name {step.name} already exists")
        self.steps[step.name] = step
        return self

    def add_watcher(self, watcher: Callable) -> None:
        """Register a watcher to receive pipeline execution callbacks."""
        self._watchers.append(watcher)

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
        in_degree = {name: 0 for name in self.steps}
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
        logger.info(f"Running pipeline {self.name}")
        self._execution_order = self._topological_sort()

        # Build shared state for watchers
        from autopipe.dashboard.state import PipelineState
        state = PipelineState(pipeline_name=self.name)
        for step in self._execution_order:
            state.add_step(step.name)

        # Notify before any step runs
        for w in self._watchers:
            try:
                w.before_pipeline(state)
            except Exception as e:
                logger.warning(f"Watcher before_pipeline failed: {e}")

        # Map step outputs
        outputs: Dict[str, Any] = {}
        if initial_inputs:
            outputs.update(initial_inputs)

        for step in self._execution_order:
            # Gather outputs of declared dependencies as inputs
            if step.depends_on:
                inputs = {dep: outputs[dep] for dep in step.depends_on if dep in outputs}
            else:
                inputs = dict(initial_inputs or {})

            # Notify before step
            state.start_step(step.name)
            for w in self._watchers:
                try:
                    w.before_step(state, step.name)
                except Exception as e:
                    logger.warning(f"Watcher before_step failed: {e}")

            logger.info(f"Running step {step.name}")
            try:
                step_output = step.run(**inputs)
                outputs[step.name] = step_output
                state.finish_step(step.name, step_output)

                # Notify after step
                for w in self._watchers:
                    try:
                        w.after_step(state, step.name, step_output)
                    except Exception as e:
                        logger.warning(f"Watcher after_step failed: {e}")

            except Exception as e:
                state.fail_step(step.name, e)
                for w in self._watchers:
                    try:
                        w.on_error(state, step.name, e)
                    except Exception as w_err:
                        logger.warning(f"Watcher on_error failed: {w_err}")
                raise

            # Generate visualizations
            try:
                step.visualize(**inputs)
            except Exception as e:
                logger.warning(f"Visualization failed for step {step.name}: {e}")

        state.state = "completed"
        state.pipeline_output = outputs

        # Notify after all steps
        for w in self._watchers:
            try:
                w.after_pipeline(state)
            except Exception as e:
                logger.warning(f"Watcher after_pipeline failed: {e}")

        logger.info(f"Pipeline {self.name} completed")
        return outputs

    def visualize_all(self):
        """Generate visualizations for all steps."""
        for step in self.steps.values():
            try:
                step.visualize()
            except Exception as e:
                logger.warning(f"Visualization failed for step {step.name}: {e}")
