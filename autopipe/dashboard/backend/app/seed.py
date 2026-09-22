"""Seed the database with initial data for development/testing.

WARNING: This script creates demo users with hardcoded passwords.
Only use in development/testing environments. Do NOT run in production.
"""

import asyncio
import logging
import uuid

from app.core.auth import get_password_hash
from app.db.models import (
    ActivityLog,
    AlertSeverity,
    ChartArtifact,
    DashboardMetric,
    DriftAlert,
    DriftReport,
    Experiment,
    MetricLog,
    Model,
    ModelStage,
    ModelVersion,
    Pipeline,
    Project,
    Run,
    RunStatus,
    Step,
    StepStatus,
    User,
    UserRole,
)
from app.db.session import AsyncSessionLocal
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from autopipe.schemas.models import PipelineConfig, StepConfig

logger = logging.getLogger(__name__)


def _seed_pipeline_config(name: str, description: str) -> dict:
    """Build a minimal executable pipeline config that passes run admission."""
    return PipelineConfig(
        name=name,
        description=description,
        steps=[
            StepConfig(name="load_data", type="sample_data_loader", params={"dataset": "iris"}),
            StepConfig(
                name="summarize",
                type="print",
                depends_on=["load_data"],
                inputs={"data": "load_data"},
            ),
        ],
    ).model_dump()


# Module-level so admission tests can exercise every seed config through
# `admit_run_config` without seeding the database first.
PIPELINE_SEEDS: list[dict] = [
    {
        "name": name,
        "description": description,
        "config": _seed_pipeline_config(name, description),
        "tags": tags,
        "created_by_index": created_by_index,
        "project_index": project_index,
    }
    for name, description, tags, created_by_index, project_index in [
        (
            "customer_churn_training",
            "End-to-end pipeline for customer churn prediction model training",
            ["production", "ml", "churn"],
            1,
            0,
        ),
        (
            "fraud_detection_pipeline",
            "Real-time fraud detection with feature engineering",
            ["production", "fraud", "realtime"],
            2,
            1,
        ),
        (
            "recommendation_engine",
            "Collaborative filtering recommendation system",
            ["staging", "recommendations"],
            1,
            2,
        ),
        (
            "data_preprocessing",
            "Data cleaning and feature engineering pipeline",
            ["utility", "data"],
            0,
            0,
        ),
        (
            "model_evaluation",
            "A/B testing and model evaluation pipeline",
            ["evaluation", "testing"],
            2,
            1,
        ),
        (
            "hyperparam_tuning",
            "Optuna-based hyperparameter optimization",
            ["optimization", "optuna"],
            1,
            3,
        ),
    ]
]


async def seed_projects(db: AsyncSession) -> list[Project]:
    """Create sample projects."""
    projects_data = [
        {
            "name": "Image Classification",
            "description": "ResNet-50 on ImageNet subset",
            "status": "active",
            "tags": ["cv", "classification"],
            "starred": True,
        },
        {
            "name": "NLP Sentiment",
            "description": "BERT fine-tuning for sentiment analysis",
            "status": "active",
            "tags": ["nlp", "bert"],
            "starred": False,
        },
        {
            "name": "Time Series Forecast",
            "description": "LSTM for demand prediction",
            "status": "active",
            "tags": ["forecasting", "lstm"],
            "starred": False,
        },
        {
            "name": "Anomaly Detection",
            "description": "Isolation forest on logs",
            "status": "archived",
            "tags": ["anomaly", "unsupervised"],
            "starred": False,
        },
    ]

    projects: list[Project] = []
    created = 0
    for data in projects_data:
        result = await db.execute(select(Project).where(Project.name == data["name"]))
        existing = result.scalars().first()
        if existing:
            projects.append(existing)
        else:
            project = Project(
                id=str(uuid.uuid4()),
                name=data["name"],
                description=data["description"],
                status=data["status"],
                tags=data["tags"],
                starred=data["starred"],
            )
            db.add(project)
            projects.append(project)
            created += 1

    await db.commit()
    logger.info(f"  ✓ Created {created} projects, {len(projects_data) - created} already existed")
    return projects


async def seed_users(db: AsyncSession) -> None:
    """Create initial users.

    Passwords below are well-known demo credentials for local seeding only;
    never seed production users from this function without replacing them.
    """
    users_data = [
        {
            "username": "admin",
            "email": "admin@autopipe.io",
            "full_name": "System Administrator",
            "password": "admin123",  # nosec B105 — local demo seed credential
            "role": UserRole.ADMIN,
            "is_active": True,
        },
        {
            "username": "data_scientist",
            "email": "ds@autopipe.io",
            "full_name": "Jane Data Scientist",
            "password": "ds123456",  # nosec B105 — local demo seed credential
            "role": UserRole.DATA_SCIENTIST,
            "is_active": True,
        },
        {
            "username": "ml_engineer",
            "email": "ml@autopipe.io",
            "full_name": "John ML Engineer",
            "password": "ml123456",  # nosec B105 — local demo seed credential
            "role": UserRole.DATA_SCIENTIST,
            "is_active": True,
        },
        {
            "username": "viewer",
            "email": "viewer@autopipe.io",
            "full_name": "Bob Viewer",
            "password": "viewer123",  # nosec B105 — local demo seed credential
            "role": UserRole.VIEWER,
            "is_active": True,
        },
    ]

    created = 0
    for ud in users_data:
        result = await db.execute(select(User).where(User.email == ud["email"]))
        if result.scalars().first() is None:
            db.add(
                User(
                    id=str(uuid.uuid4()),
                    username=ud["username"],
                    email=ud["email"],
                    full_name=ud["full_name"],
                    hashed_password=get_password_hash(ud["password"]),
                    role=ud["role"],
                    is_active=ud["is_active"],
                )
            )
            created += 1

    await db.commit()
    logger.info(f"  ✓ Created {created} users, {len(users_data) - created} already existed")


async def seed_pipelines(
    db: AsyncSession, users: list[User], projects: list[Project]
) -> list[Pipeline]:
    """Create sample pipelines linked to projects."""
    pipelines_data = PIPELINE_SEEDS

    pipelines = []
    created = 0
    for data in pipelines_data:
        result = await db.execute(select(Pipeline).where(Pipeline.name == data["name"]))
        existing = result.scalars().first()
        if existing:
            pipelines.append(existing)
        else:
            project = (
                projects[data["project_index"]]
                if data.get("project_index") is not None and data["project_index"] < len(projects)
                else None
            )
            pipeline = Pipeline(
                id=str(uuid.uuid4()),
                name=data["name"],
                description=data["description"],
                config=data["config"],
                tags=data["tags"],
                created_by=users[data["created_by_index"]].id,
                is_active=True,
                project_id=project.id if project else None,
            )
            db.add(pipeline)
            pipelines.append(pipeline)
            created += 1

    await db.commit()
    logger.info(f"  ✓ Created {created} pipelines, {len(pipelines_data) - created} already existed")
    return pipelines


async def seed_runs(
    db: AsyncSession, pipelines: list[Pipeline], experiments: list[Experiment] | None = None
) -> None:
    """Create sample pipeline runs, optionally linked to experiments."""
    # Skip if runs already exist
    existing_count = await db.scalar(select(sa_func.count(Run.id)))
    if existing_count and existing_count > 0:
        logger.info(f"  ✓ Runs already exist ({existing_count}), skipping")
        return

    import random
    from datetime import datetime, timedelta, timezone

    statuses = [
        RunStatus.SUCCESS,
        RunStatus.SUCCESS,
        RunStatus.SUCCESS,
        RunStatus.FAILED,
        RunStatus.RUNNING,
    ]
    runs_created = 0

    for p_idx, pipeline in enumerate(pipelines[:3]):
        experiment_id = experiments[p_idx].id if experiments and p_idx < len(experiments) else None
        # Create 5 runs per pipeline
        for i in range(5):
            started = datetime.now(timezone.utc) - timedelta(
                days=random.randint(0, 7), hours=random.randint(0, 12)
            )
            status = statuses[i]

            if status == RunStatus.SUCCESS:
                duration = random.uniform(60, 600)
                completed = started + timedelta(seconds=duration)
            elif status == RunStatus.FAILED:
                duration = random.uniform(30, 300)
                completed = started + timedelta(seconds=duration)
            else:
                completed = None
                duration = None

            run = Run(
                id=str(uuid.uuid4()),
                pipeline_id=pipeline.id,
                experiment_id=experiment_id,
                project_id=pipeline.project_id,
                run_number=i + 1,
                status=status,
                started_at=started,
                completed_at=completed,
                duration_seconds=duration,
                config={"override": f"run_{i}"},
                metrics={
                    "loss": round(random.uniform(0.05, 0.35), 4),
                    "accuracy": round(random.uniform(0.85, 0.97), 4),
                    "f1": round(random.uniform(0.83, 0.95), 4),
                    "precision": round(random.uniform(0.82, 0.96), 4),
                    "recall": round(random.uniform(0.80, 0.94), 4),
                    "cpu_percent": round(random.uniform(15, 85), 1),
                    "memory_percent": round(random.uniform(30, 75), 1),
                    "gpu_percent": round(random.uniform(10, 95), 1)
                    if random.random() > 0.3
                    else None,
                }
                if status == RunStatus.SUCCESS
                else None,
                error_message="Connection timeout after 30s"
                if status == RunStatus.FAILED
                else None,
            )
            db.add(run)
            runs_created += 1

            # Add steps for each run
            step_names = ["load_data", "preprocess", "train", "evaluate", "save"]
            for j, step_name in enumerate(step_names):
                step_status = (
                    StepStatus.SUCCESS
                    if status == RunStatus.SUCCESS
                    else (
                        StepStatus.FAILED
                        if step_name == "train" and status == RunStatus.FAILED
                        else StepStatus.SUCCESS
                    )
                )
                step_started = started + timedelta(minutes=j * 2)
                step_completed = step_started + timedelta(minutes=random.uniform(1, 3))

                step = Step(
                    id=str(uuid.uuid4()),
                    run_id=run.id,
                    name=step_name,
                    step_type=f"{step_name.title()}Step",
                    status=step_status,
                    started_at=step_started,
                    completed_at=step_completed,
                    duration_seconds=(step_completed - step_started).total_seconds(),
                    order_index=j,
                    logs=f"[INFO] {step_name}: Processing data...\n[INFO] {step_name}: Done!",
                    metrics={"step_metric": round(random.uniform(0.8, 1.0), 3)}
                    if step_status == StepStatus.SUCCESS
                    else None,
                )
                db.add(step)

    await db.commit()
    logger.info(f"  ✓ Created {runs_created} runs with steps")


async def seed_models(db: AsyncSession, users: list[User]) -> None:
    """Create sample models and versions."""
    models_data = [
        {
            "name": "customer_churn_model",
            "description": "XGBoost-based customer churn prediction",
            "framework": "xgboost",
            "task_type": "classification",
            "tags": ["production", "churn", "xgboost"],
            "stages": ["production", "staging", "pending"],
            "metrics": [
                {"accuracy": 0.942, "f1": 0.925},
                {"accuracy": 0.931, "f1": 0.912},
                {"accuracy": 0.918, "f1": 0.898},
            ],
        },
        {
            "name": "fraud_detection_model",
            "description": "Random Forest fraud detection",
            "framework": "sklearn",
            "task_type": "classification",
            "tags": ["production", "fraud"],
            "stages": ["production", "staging"],
            "metrics": [{"auc": 0.978, "f1": 0.885}, {"auc": 0.965, "f1": 0.862}],
        },
        {
            "name": "recommendation_model",
            "description": "Matrix factorization recommendation engine",
            "framework": "pytorch",
            "task_type": "recommendation",
            "tags": ["staging", "recommendations"],
            "stages": ["staging", "staging"],
            "metrics": [{"ndcg@10": 0.623}, {"ndcg@10": 0.598}],
        },
        {
            "name": "sentiment_analysis",
            "description": "BERT-based sentiment classification",
            "framework": "pytorch",
            "task_type": "classification",
            "tags": ["pending", "nlp"],
            "stages": ["pending"],
            "metrics": [{"accuracy": 0.912, "f1": 0.908}],
        },
    ]

    created = 0
    for model_data in models_data:
        result = await db.execute(select(Model).where(Model.name == model_data["name"]))
        if result.scalars().first() is not None:
            continue

        model = Model(
            id=str(uuid.uuid4()),
            name=model_data["name"],
            description=model_data["description"],
            framework=model_data["framework"],
            task_type=model_data["task_type"],
            tags=model_data["tags"],
            current_stage=ModelStage(model_data["stages"][0]),
        )
        db.add(model)
        created += 1

        # Create versions
        for i, (stage, metrics) in enumerate(
            zip(model_data["stages"], model_data["metrics"], strict=False)
        ):
            version = ModelVersion(
                id=str(uuid.uuid4()),
                model_id=model.id,
                version=i + 1,
                stage=ModelStage(stage),
                metrics=metrics,
                params={"n_estimators": 100 * (i + 1), "learning_rate": 0.1},
                artifact_path=f"/artifacts/{model_data['name']}/v{i + 1}.pkl",
                run_id=str(uuid.uuid4()),
            )
            db.add(version)

    await db.commit()
    logger.info(
        f"  ✓ Created {created} models with versions, {len(models_data) - created} already existed"
    )


async def seed_experiments(db: AsyncSession, users: list[User]) -> list[Experiment]:
    """Create sample experiments and return them for linking to runs."""
    experiments_data = [
        {
            "name": "churn_hyperparam_search",
            "description": "Optuna-based hyperparameter optimization for churn model",
            "config": {
                "search_space": {
                    "n_estimators": {"type": "int", "low": 50, "high": 300},
                    "learning_rate": {"type": "float", "low": 0.01, "high": 0.2},
                    "max_depth": {"type": "int", "low": 3, "high": 10},
                },
                "direction": "maximize",
                "metric": "val_accuracy",
            },
            "tags": ["optuna", "hyperparameter"],
            "best_metric": 0.948,
        },
        {
            "name": "fraud_threshold_tuning",
            "description": "Find optimal fraud classification threshold",
            "config": {
                "threshold_range": {"low": 0.5, "high": 0.95},
                "metric": "f1",
            },
            "tags": ["threshold", "optimization"],
            "best_metric": 0.891,
        },
        {
            "name": "recommendation_factor_search",
            "description": "Find optimal latent factors for recommendation",
            "config": {
                "factors": {"low": 10, "high": 100},
                "regularization": {"low": 0.001, "high": 0.1},
            },
            "tags": ["recommendation", "als"],
            "best_metric": 0.641,
        },
    ]

    experiments = []
    created = 0
    for data in experiments_data:
        result = await db.execute(select(Experiment).where(Experiment.name == data["name"]))
        existing = result.scalars().first()
        if existing:
            experiments.append(existing)
        else:
            experiment = Experiment(
                id=str(uuid.uuid4()),
                name=data["name"],
                description=data["description"],
                config=data["config"],
                tags=data["tags"],
                created_by=users[1].id,
                best_metric=data["best_metric"],
                metric_name="accuracy",
            )
            db.add(experiment)
            experiments.append(experiment)
            created += 1

    await db.commit()
    logger.info(
        f"  ✓ Created {created} experiments, {len(experiments_data) - created} already existed"
    )
    return experiments


async def seed_drift_reports(db: AsyncSession) -> None:
    """Create sample drift reports and alerts."""
    existing = await db.scalar(select(sa_func.count(DriftReport.id)))
    if existing and existing > 0:
        logger.info(f"  ✓ Drift reports already exist ({existing}), skipping")
        return

    # Drift report
    report = DriftReport(
        id=str(uuid.uuid4()),
        drift_score=0.28,
        drift_detected=True,
        feature_drifts={
            "avg_session_duration": {"psi": 0.31, "p_value": 0.002},
            "transaction_count": {"psi": 0.24, "p_value": 0.015},
            "account_age": {"psi": 0.18, "p_value": 0.08},
        },
        reference_data_summary={"rows": 50000, "columns": 25},
        current_data_summary={"rows": 50000, "columns": 25},
        alert_generated=True,
    )
    db.add(report)

    # Drift alerts
    alerts_data = [
        {
            "feature_name": "avg_session_duration",
            "severity": AlertSeverity.WARNING,
            "drift_score": 0.31,
        },
        {
            "feature_name": "transaction_count",
            "severity": AlertSeverity.WARNING,
            "drift_score": 0.24,
        },
        {"feature_name": "account_age", "severity": AlertSeverity.INFO, "drift_score": 0.18},
    ]

    for alert_data in alerts_data:
        alert = DriftAlert(
            id=str(uuid.uuid4()),
            drift_report_id=report.id,
            feature_name=alert_data["feature_name"],
            severity=alert_data["severity"],
            drift_type="feature",
            drift_metric="psi",
            drift_score=alert_data["drift_score"],
            threshold=0.2,
            acknowledged=alert_data["drift_score"] < 0.25,
        )
        db.add(alert)

    await db.commit()
    logger.info("  ✓ Created drift reports and alerts")


async def seed_dashboard_metrics(db: AsyncSession) -> None:
    """Create sample dashboard metrics."""
    existing = await db.scalar(select(sa_func.count(DashboardMetric.id)))
    if existing and existing > 0:
        logger.info(f"  ✓ Dashboard metrics already exist ({existing}), skipping")
        return

    import random
    from datetime import datetime, timedelta, timezone

    metric_names = ["pipeline_success_rate", "avg_run_duration", "model_accuracy", "active_runs"]

    for metric_name in metric_names:
        for days_ago in range(14):
            timestamp = datetime.now(timezone.utc) - timedelta(days=days_ago)
            # Vary value slightly each day
            base_values = {
                "pipeline_success_rate": 0.92,
                "avg_run_duration": 180,
                "model_accuracy": 0.94,
                "active_runs": 12,
            }
            base = base_values.get(metric_name, 0.5)
            value = base + random.uniform(-0.05, 0.05)

            metric = DashboardMetric(
                id=str(uuid.uuid4()),
                metric_name=metric_name,
                metric_value=max(0, value),
                metric_type="gauge",
                recorded_at=timestamp,
            )
            db.add(metric)

    await db.commit()
    logger.info("  ✓ Created dashboard metrics")


async def seed_activity_logs(db: AsyncSession, users: list[User]) -> None:
    """Create sample activity logs."""
    existing = await db.scalar(select(sa_func.count(ActivityLog.id)))
    if existing and existing > 0:
        logger.info(f"  ✓ Activity logs already exist ({existing}), skipping")
        return

    import random
    from datetime import datetime, timedelta, timezone

    activities = [
        {
            "action": "run_completed",
            "resource_type": "run",
            "title": "Pipeline 'customer_churn_training' completed successfully",
        },
        {
            "action": "model_promoted",
            "resource_type": "model",
            "title": "Model 'customer_churn_model' promoted to PRODUCTION",
        },
        {
            "action": "drift_alert",
            "resource_type": "drift",
            "title": "Data drift detected: feature 'avg_session_duration'",
        },
        {
            "action": "experiment_started",
            "resource_type": "experiment",
            "title": "Experiment 'churn_hyperparam_search' started",
        },
        {
            "action": "run_failed",
            "resource_type": "run",
            "title": "Pipeline 'fraud_detection_pipeline' failed",
        },
        {
            "action": "model_registered",
            "resource_type": "model",
            "title": "New model 'sentiment_analysis' registered",
        },
    ]

    for i, activity_data in enumerate(activities):
        activity = ActivityLog(
            id=str(uuid.uuid4()),
            user_id=users[random.randint(0, len(users) - 1)].id,
            action=activity_data["action"],
            resource_type=activity_data["resource_type"],
            resource_id=str(uuid.uuid4()),
            details={"title": activity_data["title"], "description": "Automated system event"},
            created_at=datetime.now(timezone.utc) - timedelta(hours=i * 2 + 1),
        )
        db.add(activity)

    await db.commit()
    logger.info("  ✓ Created activity logs")


async def seed_chart_artifacts(db: AsyncSession) -> None:
    """Create sample chart artifacts for seeded runs."""
    existing = await db.scalar(select(sa_func.count(ChartArtifact.id)))
    if existing and existing > 0:
        logger.info(f"  ✓ Chart artifacts already exist ({existing}), skipping")
        return

    import random

    result = await db.execute(select(Run).where(Run.status == RunStatus.SUCCESS).limit(5))
    runs = list(result.scalars().all())
    if not runs:
        logger.info("  ⚠ No successful runs found, skipping chart artifacts")
        return

    templates = [
        {
            "chart_type": "line",
            "title": "Training Loss",
            "data": {
                "x_key": "epoch",
                "series": ["loss", "val_loss"],
                "points": [
                    {
                        "epoch": e,
                        "loss": round(0.5 * (0.9**e) + random.uniform(0, 0.02), 4),
                        "val_loss": round(0.55 * (0.88**e) + random.uniform(0, 0.03), 4),
                    }
                    for e in range(1, 11)
                ],
            },
            "config": {
                "x_label": "Epoch",
                "y_label": "Loss",
                "colors": {"loss": "#ef4444", "val_loss": "#3b82f6"},
            },
        },
        {
            "chart_type": "line",
            "title": "Accuracy Over Epochs",
            "data": {
                "x_key": "epoch",
                "series": ["accuracy", "val_accuracy"],
                "points": [
                    {
                        "epoch": e,
                        "accuracy": round(min(0.99, 0.6 + 0.04 * e + random.uniform(0, 0.01)), 4),
                        "val_accuracy": round(
                            min(0.98, 0.58 + 0.038 * e + random.uniform(0, 0.015)), 4
                        ),
                    }
                    for e in range(1, 11)
                ],
            },
            "config": {
                "x_label": "Epoch",
                "y_label": "Accuracy",
                "domain": [0.5, 1],
                "colors": {"accuracy": "#10b981", "val_accuracy": "#8b5cf6"},
            },
        },
        {
            "chart_type": "bar",
            "title": "Feature Importance",
            "data": {
                "x_key": "feature",
                "series": ["importance"],
                "points": [
                    {"feature": f, "importance": round(random.uniform(0.01, 0.35), 4)}
                    for f in [
                        "age",
                        "tenure",
                        "monthly_charges",
                        "total_charges",
                        "contract_type",
                        "payment_method",
                        "internet_service",
                        "tech_support",
                    ]
                ],
            },
            "config": {"layout": "vertical", "colors": {"importance": "#3b82f6"}},
        },
        {
            "chart_type": "scatter",
            "title": "Predicted vs Actual",
            "data": {
                "x_key": "actual",
                "series": ["predicted"],
                "points": [
                    {"actual": round(a, 2), "predicted": round(a + random.uniform(-0.1, 0.1), 2)}
                    for a in [0.1 * i for i in range(1, 21)]
                ],
            },
            "config": {
                "x_label": "Actual",
                "y_label": "Predicted",
                "colors": {"predicted": "#3b82f6"},
            },
        },
        {
            "chart_type": "bar",
            "title": "Class Distribution",
            "data": {
                "x_key": "class",
                "series": ["count"],
                "points": [
                    {"class": "churned", "count": random.randint(150, 300)},
                    {"class": "retained", "count": random.randint(700, 1200)},
                ],
            },
            "config": {"colors": {"count": "#8b5cf6"}},
        },
    ]

    created = 0
    for run in runs:
        for template in templates:
            artifact = ChartArtifact(
                id=str(uuid.uuid4()),
                run_id=run.id,
                experiment_id=run.experiment_id,
                chart_type=template["chart_type"],
                title=template["title"],
                data=template["data"],
                config=template.get("config"),
            )
            db.add(artifact)
            created += 1

    await db.commit()
    logger.info(f"  ✓ Created {created} chart artifacts")


async def seed_metric_logs(db: AsyncSession) -> None:
    """Create sample metric logs with training curves for successful runs."""
    existing = await db.scalar(select(sa_func.count(MetricLog.id)))
    if existing and existing > 0:
        logger.info(f"  ✓ Metric logs already exist ({existing}), skipping")
        return

    import random
    from datetime import datetime, timedelta, timezone

    result = await db.execute(select(Run).where(Run.status == RunStatus.SUCCESS).limit(10))
    runs = list(result.scalars().all())
    if not runs:
        logger.info("  ⚠ No successful runs found, skipping metric logs")
        return

    created = 0
    for idx, run in enumerate(runs):
        base_time = run.started_at or datetime.now(timezone.utc)
        for epoch in range(1, 11):
            timestamp = base_time + timedelta(minutes=epoch)
            loss = round(0.5 * (0.9**epoch) + random.uniform(0, 0.02), 4)
            val_loss = round(0.55 * (0.88**epoch) + random.uniform(0, 0.03), 4)
            accuracy = round(min(0.99, 0.6 + 0.04 * epoch + random.uniform(0, 0.01)), 4)
            val_accuracy = round(min(0.98, 0.58 + 0.038 * epoch + random.uniform(0, 0.015)), 4)

            # Alternate between standard names and prefixed names per run
            if idx % 2 == 0:
                metric_pairs = [
                    ("loss", loss),
                    ("val_loss", val_loss),
                    ("accuracy", accuracy),
                    ("val_accuracy", val_accuracy),
                ]
            else:
                metric_pairs = [
                    ("train/epoch_loss", loss),
                    ("val_loss", val_loss),
                    ("train/epoch_accuracy", accuracy),
                    ("val_accuracy", val_accuracy),
                ]

            for metric_name, value in metric_pairs:
                db.add(
                    MetricLog(
                        id=str(uuid.uuid4()),
                        run_id=run.id,
                        pipeline_id=run.pipeline_id,
                        experiment_id=run.experiment_id,
                        metric_name=metric_name,
                        step_index=epoch,
                        value=value,
                        recorded_at=timestamp,
                    )
                )
                created += 1

    await db.commit()
    logger.info(f"  ✓ Created {created} metric logs")


async def main() -> None:
    """Run all seeders."""
    logger.info("\n🌱 Seeding database with initial data...")
    logger.info("=" * 50)

    async with AsyncSessionLocal() as db:
        # Seed users first
        await seed_users(db)

        # Get users for references
        from sqlalchemy import select

        result = await db.execute(select(User))
        users = list(result.scalars().all())

        # Seed projects
        projects = await seed_projects(db)

        # Seed pipelines
        pipelines = await seed_pipelines(db, users, projects)

        # Seed experiments before runs so runs can link to them
        experiments = await seed_experiments(db, users)

        # Seed runs (linked to experiments)
        await seed_runs(db, pipelines, experiments)

        # Seed models
        await seed_models(db, users)

        # Seed drift data
        await seed_drift_reports(db)

        # Seed dashboard metrics
        await seed_dashboard_metrics(db)

        # Seed activity logs
        await seed_activity_logs(db, users)

        # Seed chart artifacts
        await seed_chart_artifacts(db)

        # Seed metric logs (training curves)
        await seed_metric_logs(db)

    logger.info("=" * 50)
    logger.info("✅ Database seeded successfully!")
    logger.info("\n📋 Default credentials:")
    logger.info("   admin / admin123")
    logger.info("   data_scientist / ds123456")
    logger.info("   ml_engineer / ml123456")
    logger.info("   viewer / viewer123")


if __name__ == "__main__":
    asyncio.run(main())
