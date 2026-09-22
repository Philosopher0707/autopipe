import sys

sys.path.insert(0, ".")

from autopipe import Pipeline
from autopipe.core.steps import PrintStep

pipeline = Pipeline("test")
pipeline.add_step(PrintStep("step1", message="Hello"))
pipeline.add_step(PrintStep("step2", message="World", depends_on=["step1"]))

outputs = pipeline.run()
print("Outputs:", outputs)
