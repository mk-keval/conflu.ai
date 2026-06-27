"""Parameter optimization engine — Grid, Random, and Bayesian (Optuna) search.

Provides a unified interface for three optimization methods:
1. Grid search: Exhaustive enumeration of all parameter combinations
2. Random search: Random sampling from defined distributions
3. Bayesian optimization: Optuna TPESampler with pruning and multi-objective

All CPU-bound work runs via loop.run_in_executor() for async compatibility.
"""

from __future__ import annotations

import asyncio
import itertools
import time
from typing import Any

import numpy as np

from backend.app.core.logging import get_logger
from backend.app.infrastructure.backtest.models import (
    BacktestRunConfig,
    Metrics,
    OptimizationResultV2,
    OptimizationSearchSpace,
    TrialResult,
)

log = get_logger("conflu.backtest.optimization")


class BacktestOptimizer:
    """Parameter optimization engine supporting grid, random, and Bayesian methods.

    Wraps a BacktestEngine to evaluate parameter configurations and find
    optimal values for the specified objective metrics.
    """

    def __init__(self, engine: Any | None = None) -> None:
        self._engine = engine
        self._log = get_logger("conflu.backtest.optimization")

    async def optimize(
        self,
        config: BacktestRunConfig,
        search_space: OptimizationSearchSpace,
    ) -> OptimizationResultV2:
        """Run parameter optimization.

        Args:
            config: Base backtest configuration.
            search_space: Search space definition with method, params, objectives.

        Returns:
            OptimizationResultV2 with best params, trials, and parameter importance.
        """
        loop = asyncio.get_running_loop()
        start_time = time.monotonic()

        self._log.info(
            "optimization_started",
            method=search_space.method,
            symbol=config.symbols,
            objectives=search_space.objectives,
            max_trials=search_space.max_trials,
        )

        result = await loop.run_in_executor(
            None,
            self._optimize_sync,
            config,
            search_space,
        )

        duration_ms = (time.monotonic() - start_time) * 1000
        object.__setattr__(result, "duration_ms", duration_ms)
        self._log.info(
            "optimization_completed",
            method=search_space.method,
            trials=result.n_trials,
            best=result.best_objectives,
            duration_ms=round(duration_ms, 2),
        )
        return result

    def _optimize_sync(
        self,
        config: BacktestRunConfig,
        search_space: OptimizationSearchSpace,
    ) -> OptimizationResultV2:
        """Synchronous optimization (runs in thread pool)."""
        if self._engine is None:
            from backend.app.infrastructure.backtest.engine import BacktestEngine

            self._engine = BacktestEngine()

        if search_space.method == "grid":
            return self._grid_search(config, search_space)
        elif search_space.method == "random":
            return self._random_search(config, search_space)
        elif search_space.method == "bayesian":
            return self._bayesian_optimize(config, search_space)
        else:
            msg = f"Unknown method: '{search_space.method}'"
            raise ValueError(msg)

    def _grid_search(
        self,
        config: BacktestRunConfig,
        search_space: OptimizationSearchSpace,
    ) -> OptimizationResultV2:
        """Exhaustive grid search over all parameter combinations."""
        if not search_space.grid_params:
            raise ValueError("grid_params must be non-empty for grid search")

        param_keys = list(search_space.grid_params.keys())
        param_values = list(search_space.grid_params.values())
        param_combos = list(itertools.product(*param_values))
        objective_metric = search_space.objectives[0] if search_space.objectives else "sharpe"

        best_objective = -float("inf")
        best_params: dict[str, Any] = {}
        best_objectives: dict[str, float | None] = {}
        trials: list[TrialResult] = []

        for i, combo in enumerate(param_combos):
            params = dict(zip(param_keys, combo))
            trial_start = time.monotonic()
            metrics = self._evaluate_params(config, params)
            obj_value = self._get_objective_value(metrics, objective_metric)
            obj_values = {objective_metric: obj_value}
            trial_duration = (time.monotonic() - trial_start) * 1000
            trials.append(
                TrialResult(
                    trial_number=i,
                    params=params,
                    objectives=obj_values,
                    state="complete",
                    duration_ms=trial_duration,
                )
            )
            if obj_value is not None and obj_value > best_objective:
                best_objective = obj_value
                best_params = params
                best_objectives = obj_values

        return OptimizationResultV2(
            study_id=f"grid_{config.run_id}",
            symbol=",".join(config.symbols),
            method="grid",
            search_space=search_space,
            best_params=best_params,
            best_objectives=best_objectives,
            trials=trials,
            n_trials=len(trials),
            duration_ms=0.0,
        )

    def _random_search(
        self,
        config: BacktestRunConfig,
        search_space: OptimizationSearchSpace,
    ) -> OptimizationResultV2:
        """Random search sampling from parameter distributions."""
        if not search_space.param_distributions:
            raise ValueError("param_distributions must be non-empty for random search")

        objective_metric = search_space.objectives[0] if search_space.objectives else "sharpe"
        best_objective = -float("inf")
        best_params: dict[str, Any] = {}
        best_objectives: dict[str, float | None] = {}
        trials: list[TrialResult] = []
        n_trials = min(search_space.max_trials, 100_000)

        for i in range(n_trials):
            params = self._sample_from_distributions(search_space.param_distributions)
            trial_start = time.monotonic()
            metrics = self._evaluate_params(config, params)
            obj_value = self._get_objective_value(metrics, objective_metric)
            obj_values = {objective_metric: obj_value}
            trial_duration = (time.monotonic() - trial_start) * 1000
            trials.append(
                TrialResult(
                    trial_number=i,
                    params=params,
                    objectives=obj_values,
                    state="complete",
                    duration_ms=trial_duration,
                )
            )
            if obj_value is not None and obj_value > best_objective:
                best_objective = obj_value
                best_params = params
                best_objectives = obj_values

            # Early stopping
            if search_space.early_stopping and i > 20:
                recent = [t.objectives.get(objective_metric, 0) or 0 for t in trials[-10:]]
                if max(recent) - min(recent) < search_space.min_improvement:
                    self._log.info("random_early_stop", trials=i)
                    break

        return OptimizationResultV2(
            study_id=f"random_{config.run_id}",
            symbol=",".join(config.symbols),
            method="random",
            search_space=search_space,
            best_params=best_params,
            best_objectives=best_objectives,
            trials=trials,
            n_trials=len(trials),
            duration_ms=0.0,
        )

    def _bayesian_optimize(
        self,
        config: BacktestRunConfig,
        search_space: OptimizationSearchSpace,
    ) -> OptimizationResultV2:
        """Bayesian optimization using Optuna TPESampler."""
        try:
            import optuna
        except ImportError:
            self._log.warning("optuna_not_installed_falling_back_to_random")
            return self._random_search(config, search_space)

        objective_metric = search_space.objectives[0]
        n_trials = min(search_space.max_trials, 100_000)

        if search_space.multi_objective and len(search_space.objectives) > 1:
            study = optuna.create_study(
                directions=["maximize"] * len(search_space.objectives),
                sampler=optuna.samplers.NSGAIISampler(),
                study_name=f"backtest_{config.run_id[:8]}",
            )
        else:
            study = optuna.create_study(
                direction="maximize",
                sampler=optuna.samplers.TPESampler(
                    n_startup_trials=10,
                    multivariate=True,
                    seed=42,
                ),
                pruner=optuna.pruners.MedianPruner(
                    n_startup_trials=5,
                    n_warmup_steps=10,
                    interval_steps=1,
                )
                if search_space.early_stopping
                else optuna.pruners.NopPruner(),
                study_name=f"backtest_{config.run_id[:8]}",
            )

        def objective(trial: optuna.Trial) -> float | list[float]:
            params = self._suggest_from_optuna(trial, search_space)
            metrics = self._evaluate_params(config, params)
            if search_space.multi_objective and len(search_space.objectives) > 1:
                return [(self._get_objective_value(metrics, obj) or -999.0) for obj in search_space.objectives]
            return self._get_objective_value(metrics, objective_metric) or -999.0

        study.optimize(
            objective,
            n_trials=n_trials,
            timeout=search_space.timeout_s,
            n_jobs=search_space.n_jobs,
            show_progress_bar=False,
        )

        best_params = study.best_params if study.best_trial else {}
        best_objectives: dict[str, float | None] = {}
        if study.best_trial and study.best_trial.values:
            for i, obj_name in enumerate(search_space.objectives):
                best_objectives[obj_name] = study.best_trial.values[i]

        trials: list[TrialResult] = []
        for i, trial in enumerate(study.trials):
            obj_values: dict[str, float | None] = {}
            if trial.values:
                for j, obj_name in enumerate(search_space.objectives):
                    obj_values[obj_name] = trial.values[j] if j < len(trial.values) else None
            trials.append(
                TrialResult(
                    trial_number=i,
                    params=trial.params,
                    objectives=obj_values,
                    state=str(trial.state.name),
                )
            )

        param_importance: dict[str, float] = {}
        try:
            if len(study.trials) > 10:
                from optuna.importance import get_param_importances

                importance = get_param_importances(study)
                param_importance = {k: float(v) for k, v in importance.items()}
        except Exception:
            self._log.warning("param_importance_failed")

        return OptimizationResultV2(
            study_id=study.study_name,
            symbol=",".join(config.symbols),
            method="bayesian",
            search_space=search_space,
            best_params=best_params,
            best_objectives=best_objectives,
            trials=trials,
            n_trials=len(trials),
            duration_ms=0.0,
            param_importance=param_importance,
        )

    def _evaluate_params(self, config: BacktestRunConfig, params: dict[str, Any]) -> Metrics:
        """Evaluate a single parameter set by running a backtest."""
        if self._engine is None:
            from backend.app.infrastructure.backtest.engine import BacktestEngine

            self._engine = BacktestEngine()
        modified_config = self._apply_params(config, params)
        record = self._engine._run_sync(modified_config)
        return record.metrics or Metrics()

    @staticmethod
    def _apply_params(config: BacktestRunConfig, params: dict[str, Any]) -> BacktestRunConfig:
        """Apply parameter overrides to a copy of the base config."""
        import copy

        new_config = copy.deepcopy(config)
        sizing_keys = {
            "risk_per_trade",
            "atr_multiplier",
            "kelly_fraction",
            "mode",
            "value",
            "max_position_pct",
            "win_rate",
            "avg_win_avg_loss_ratio",
        }
        for key, value in params.items():
            if key == "position_sizing" or key in ("fees_bps", "slippage_bps", "initial_cash"):
                object.__setattr__(new_config, key, value)
            elif key in sizing_keys:
                new_config.sizing_params[key] = value
            elif key.endswith("_threshold") or key.endswith("_param"):
                new_config.signal_source.indicator_params[key] = value
        return new_config

    @staticmethod
    def _get_objective_value(metrics: Metrics, objective: str) -> float | None:
        return getattr(metrics, objective, None) if metrics else None

    @staticmethod
    def _sample_from_distributions(distributions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Sample a random parameter set from defined distributions."""
        params: dict[str, Any] = {}
        for name, dist in distributions.items():
            dist_type = dist.get("type", "categorical")
            if dist_type == "int":
                low, high, step = int(dist.get("low", 0)), int(dist.get("high", 100)), int(dist.get("step", 1))
                params[name] = int(
                    np.random.choice(list(range(low, high + 1, step))) if list(range(low, high + 1, step)) else low
                )
            elif dist_type == "float":
                low, high = float(dist.get("low", 0.0)), float(dist.get("high", 1.0))
                if dist.get("log", False):
                    params[name] = float(np.exp(np.random.uniform(np.log(low + 1e-10), np.log(high + 1e-10))))
                else:
                    params[name] = float(np.random.uniform(low, high))
            else:
                choices = dist.get("choices", [])
                params[name] = str(np.random.choice(choices)) if choices else "default"
        return params

    @staticmethod
    def _suggest_from_optuna(trial: Any, search_space: OptimizationSearchSpace) -> dict[str, Any]:
        """Suggest parameters from Optuna trial based on search space."""
        params: dict[str, Any] = {}
        if search_space.param_distributions:
            for name, dist in search_space.param_distributions.items():
                dist_type = dist.get("type", "categorical")
                if dist_type == "int":
                    params[name] = trial.suggest_int(
                        name, int(dist.get("low", 0)), int(dist.get("high", 100)), step=int(dist.get("step", 1))
                    )
                elif dist_type == "float":
                    low, high = float(dist.get("low", 0.0)), float(dist.get("high", 1.0))
                    params[name] = trial.suggest_float(name, low, high, log=dist.get("log", False))
                else:
                    params[name] = trial.suggest_categorical(name, dist.get("choices", []))
        if not params and search_space.grid_params:
            for name, values in search_space.grid_params.items():
                params[name] = trial.suggest_categorical(name, values) if len(values) > 1 else values[0]
        return params
