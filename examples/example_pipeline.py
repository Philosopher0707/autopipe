#!/usr/bin/env python3
"""Example pipeline using AutoPipe."""

import sys

sys.path.insert(0, ".")

from autopipe import Pipeline, Step
from autopipe.core.steps import DataLoaderStep, LLMStep, PrintStep, VisualizationStep


# Define a custom step
class CustomStep(Step):
    def run(self, **kwargs):
        print(f"Custom step {self.name} received keys: {list(kwargs.keys())}")
        return {"processed": True}


# Build pipeline
pipeline = Pipeline("demo")

pipeline.add_step(PrintStep("start", message="Pipeline started"))
pipeline.add_step(DataLoaderStep("load_iris", dataset="iris", depends_on=["start"]))
pipeline.add_step(
    LLMStep(
        "ask_llm",
        provider="openrouter",
        prompt_template="What is the iris dataset? Explain in one sentence.",
        depends_on=["load_iris"],
    )
)
pipeline.add_step(CustomStep("custom", depends_on=["ask_llm"]))
pipeline.add_step(VisualizationStep("visualize", depends_on=["load_iris"]))

if __name__ == "__main__":
    outputs = pipeline.run()
    print("\nPipeline outputs:")
    for key, val in outputs.items():
        print(f"  {key}: {type(val).__name__}")
