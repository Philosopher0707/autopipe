"""Report generation for experiments."""

from typing import Any, Dict, List, Optional
from pathlib import Path
import json


class ReportGenerator:
    """Generate experiment reports."""
    
    def __init__(self, output_dir: str = "./reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_run_report(self, run_id: str, run_data: Dict[str, Any]) -> str:
        """Generate a report for a single run."""
        report_path = self.output_dir / f"run_{run_id}.json"
        
        report = {
            "run_id": run_id,
            "generated_at": __import__('datetime').datetime.now().isoformat(),
            "data": run_data
        }
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        return str(report_path)
    
    def generate_experiment_report(self, experiment_id: str, experiment_data: Dict[str, Any]) -> str:
        """Generate a report for an experiment."""
        report_path = self.output_dir / f"experiment_{experiment_id}.md"
        
        lines = [
            f"# Experiment Report: {experiment_data.get('name', experiment_id)}\n",
            f"**ID:** {experiment_id}\n",
            f"**Created:** {experiment_data.get('created_at', 'N/A')}\n\n",
            "## Configuration\n",
            f"```json\n{json.dumps(experiment_data.get('config', {}), indent=2)}\n```\n\n",
            "## Runs\n",
            f"Total runs: {len(experiment_data.get('runs', []))}\n"
        ]
        
        with open(report_path, 'w') as f:
            f.writelines(lines)
        
        return str(report_path)
    
    def generate_comparison_table(self, runs: List[Dict[str, Any]], metrics: List[str]) -> str:
        """Generate a comparison table for multiple runs."""
        header = "| Run |" + "|".join(metrics) + "|\n"
        separator = "|---" * (len(metrics) + 1) + "|\n"
        
        lines = [header, separator]
        
        for run in runs:
            row = f"| {run.get('run_id', 'N/A')[:8]} |"
            run_metrics = run.get('metrics', [])
            for metric_name in metrics:
                metric_value = next((m.value for m in run_metrics if m.name == metric_name), "N/A")
                row += f" {metric_value:.4f} |" if isinstance(metric_value, float) else f" {metric_value} |"
            lines.append(row + "\n")
        
        return "".join(lines)
