"""Seed the database with initial data for development/testing."""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_password_hash
from app.core.config import settings
from app.db.models import (
    User, UserRole, Pipeline, Run, RunStatus, Step, StepStatus,
    Experiment, Model, ModelVersion, ModelStage, DriftReport, DriftAlert,
    AlertSeverity, DashboardMetric, ActivityLog,
)
from app.db.session import engine, AsyncSessionLocal


async def seed_users(db: AsyncSession) -> None:
    """Create initial users."""
    users = [
        User(
            id=str(uuid.uuid4()),
            username="admin",
            email="admin@autopipe.io",
            full_name="System Administrator",
            hashed_password=get_password_hash("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
        ),
        User(
            id=str(uuid.uuid4()),
            username="data_scientist",
            email="ds@autopipe.io",
            full_name="Jane Data Scientist",
            hashed_password=get_password_hash("ds123456"),
            role=UserRole.DATA_SCIENTIST,
            is_active=True,
        ),
        User(
            id=str(uuid.uuid4()),
            username="ml_engineer",
            email="ml@autopipe.io",
            full_name="John ML Engineer",
            hashed_password=get_password_hash("ml123456"),
            role=UserRole.DATA_SCIENTIST,
            is_active=True,
        ),
        User(
            id=str(uuid.uuid4()),
            username="viewer",
            email="viewer@autopipe.io",
            full_name="Bob Viewer",
            hashed_password=get_password_hash("viewer123"),
            role=UserRole.VIEWER,
            is_active=True,
        ),
    ]
    
    for user in users:
        existing = await db.get(User, user.id)
        if not existing:
            db.add(user)
    
    await db.commit()
    print(f"  ✓ Created {len(users)} users")


async def seed_pipelines(db: AsyncSession, users: list[User]) -> list[Pipeline]:
    """Create sample pipelines."""
    pipelines_data = [
        {
            "name": "customer_churn_training",
            "description": "End-to-end pipeline for customer churn prediction model training",
            "config": {
                "model_type": "gradient_boosting",
                "features": ["tenure", "monthly_charges", "contract_type"],
                "target": "churn",
            },
            "tags": ["production", "ml", "churn"],
            "created_by": users[1].id,
        },
        {
            "name": "fraud_detection_pipeline",
            "description": "Real-time fraud detection with feature engineering",
            "config": {
                "model_type": "random_forest",
                "threshold": 0.7,
            },
            "tags": ["production", "fraud", "realtime"],
            "created_by": users[2].id,
        },
        {
            "name": "recommendation_engine",
            "description": "Collaborative filtering recommendation system",
            "config": {
                "algorithm": "als",
                "factors": 50,
            },
            "tags": ["staging", "recommendations"],
            "created_by": users[1].id,
        },
        {
            "name": "data_preprocessing",
            "description": "Data cleaning and feature engineering pipeline",
            "config": {
                "steps": ["clean", "normalize", "encode", "split"],
            },
            "tags": ["utility", "data"],
            "created_by": users[0].id,
        },
        {
            "name": "model_evaluation",
            "description": "A/B testing and model evaluation pipeline",
            "config": {
                "metrics": ["accuracy", "f1", "precision", "recall", "auc"],
            },
            "tags": ["evaluation", "testing"],
            "created_by": users[2].id,
        },
        {
            "name": "hyperparam_tuning",
            "description": "Optuna-based hyperparameter optimization",
            "config": {
                "n_trials": 100,
                "direction": "maximize",
                "metric": "val_accuracy",
            },
            "tags": ["optimization", "optuna"],
            "created_by": users[1].id,
        },
    ]
    
    pipelines = []
    for data in pipelines_data:
        pipeline = Pipeline(
            id=str(uuid.uuid4()),
            name=data["name"],
            description=data["description"],
            config=data["config"],
            tags=data["tags"],
            created_by=data["created_by"],
            is_active=True,
        )
        db.add(pipeline)
        pipelines.append(pipeline)
    
    await db.commit()
    print(f"  ✓ Created {len(pipelines)} pipelines")
    return pipelines


async def seed_runs(db: AsyncSession, pipelines: list[Pipeline]) -> None:
    """Create sample pipeline runs."""
    import random
    from datetime import datetime, timedelta
    
    statuses = [RunStatus.SUCCESS, RunStatus.SUCCESS, RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.RUNNING]
    runs_created = 0
    
    for pipeline in pipelines[:3]:
        # Create 5 runs per pipeline
        for i in range(5):
            started = datetime.utcnow() - timedelta(days=random.randint(0, 7), hours=random.randint(0, 12))
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
                status=status,
                started_at=started,
                completed_at=completed,
                duration_seconds=duration,
                config={"override": f"run_{i}"},
                metrics={
                    "accuracy": round(random.uniform(0.85, 0.97), 4),
                    "f1": round(random.uniform(0.83, 0.95), 4),
                    "precision": round(random.uniform(0.82, 0.96), 4),
                    "recall": round(random.uniform(0.80, 0.94), 4),
                } if status == RunStatus.SUCCESS else None,
                error_message="Connection timeout after 30s" if status == RunStatus.FAILED else None,
            )
            db.add(run)
            runs_created += 1
            
            # Add steps for each run
            step_names = ["load_data", "preprocess", "train", "evaluate", "save"]
            for j, step_name in enumerate(step_names):
                step_status = StepStatus.SUCCESS if status == RunStatus.SUCCESS else (
                    StepStatus.FAILED if step_name == "train" and status == RunStatus.FAILED else StepStatus.SUCCESS
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
                    metrics={"step_metric": round(random.uniform(0.8, 1.0), 3)} if step_status == StepStatus.SUCCESS else None,
                )
                db.add(step)
    
    await db.commit()
    print(f"  ✓ Created {runs_created} runs with steps")


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
            "metrics": [{"accuracy": 0.942, "f1": 0.925}, {"accuracy": 0.931, "f1": 0.912}, {"accuracy": 0.918, "f1": 0.898}],
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
    
    for model_data in models_data:
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
        
        # Create versions
        for i, (stage, metrics) in enumerate(zip(model_data["stages"], model_data["metrics"])):
            version = ModelVersion(
                id=str(uuid.uuid4()),
                model_id=model.id,
                version=i + 1,
                stage=ModelStage(stage),
                metrics=metrics,
                params={"n_estimators": 100 * (i + 1), "learning_rate": 0.1},
                artifact_path=f"/artifacts/{model_data['name']}/v{i+1}.pkl",
                run_id=str(uuid.uuid4()),
            )
            db.add(version)
    
    await db.commit()
    print(f"  ✓ Created {len(models_data)} models with versions")


async def seed_experiments(db: AsyncSession, users: list[User]) -> None:
    """Create sample experiments."""
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
    
    for data in experiments_data:
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
    
    await db.commit()
    print(f"  ✓ Created {len(experiments_data)} experiments")


async def seed_drift_reports(db: AsyncSession) -> None:
    """Create sample drift reports and alerts."""
    from datetime import datetime, timedelta
    
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
        {"feature_name": "avg_session_duration", "severity": AlertSeverity.WARNING, "drift_score": 0.31},
        {"feature_name": "transaction_count", "severity": AlertSeverity.WARNING, "drift_score": 0.24},
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
    print(f"  ✓ Created drift reports and alerts")


async def seed_dashboard_metrics(db: AsyncSession) -> None:
    """Create sample dashboard metrics."""
    from datetime import datetime, timedelta
    import random
    
    metric_names = ["pipeline_success_rate", "avg_run_duration", "model_accuracy", "active_runs"]
    
    for metric_name in metric_names:
        for days_ago in range(14):
            timestamp = datetime.utcnow() - timedelta(days=days_ago)
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
    print(f"  ✓ Created dashboard metrics")


async def seed_activity_logs(db: AsyncSession, users: list[User]) -> None:
    """Create sample activity logs."""
    from datetime import datetime, timedelta
    import random
    
    activities = [
        {"action": "run_completed", "resource_type": "run", "title": "Pipeline 'customer_churn_training' completed successfully"},
        {"action": "model_promoted", "resource_type": "model", "title": "Model 'customer_churn_model' promoted to PRODUCTION"},
        {"action": "drift_alert", "resource_type": "drift", "title": "Data drift detected: feature 'avg_session_duration'"},
        {"action": "experiment_started", "resource_type": "experiment", "title": "Experiment 'churn_hyperparam_search' started"},
        {"action": "run_failed", "resource_type": "run", "title": "Pipeline 'fraud_detection_pipeline' failed"},
        {"action": "model_registered", "resource_type": "model", "title": "New model 'sentiment_analysis' registered"},
    ]
    
    for i, activity_data in enumerate(activities):
        activity = ActivityLog(
            id=str(uuid.uuid4()),
            user_id=users[random.randint(0, len(users)-1)].id,
            action=activity_data["action"],
            resource_type=activity_data["resource_type"],
            resource_id=str(uuid.uuid4()),
            details={"title": activity_data["title"], "description": "Automated system event"},
            created_at=datetime.utcnow() - timedelta(hours=i * 2 + 1),
        )
        db.add(activity)
    
    await db.commit()
    print(f"  ✓ Created activity logs")


async def main() -> None:
    """Run all seeders."""
    print("\n🌱 Seeding database with initial data...")
    print("=" * 50)
    
    async with AsyncSessionLocal() as db:
        # Seed users first
        await seed_users(db)
        
        # Get users for references
        from sqlalchemy import select
        result = await db.execute(select(User))
        users = list(result.scalars().all())
        
        # Seed pipelines
        pipelines = await seed_pipelines(db, users)
        
        # Seed runs
        await seed_runs(db, pipelines)
        
        # Seed models
        await seed_models(db, users)
        
        # Seed experiments
        await seed_experiments(db, users)
        
        # Seed drift data
        await seed_drift_reports(db)
        
        # Seed dashboard metrics
        await seed_dashboard_metrics(db)
        
        # Seed activity logs
        await seed_activity_logs(db, users)
    
    print("=" * 50)
    print("✅ Database seeded successfully!")
    print("\n📋 Default credentials:")
    print("   admin / admin123")
    print("   data_scientist / ds123456")
    print("   ml_engineer / ml123456")
    print("   viewer / viewer123")


if __name__ == "__main__":
    asyncio.run(main())
