from __future__ import annotations

import numpy as np


def directional_accuracy(pred: list[int], actual: list[int]) -> float:
    if not pred:
        return float("nan")
    return float(np.mean(np.array(pred) == np.array(actual)))


def brier_score(prob_up: list[float], actual_up: list[int]) -> float:
    p = np.array(prob_up, dtype=float)
    y = np.array(actual_up, dtype=float)
    return float(np.mean((p - y) ** 2))


def excess_return(asset_return: list[float], benchmark_return: list[float]) -> list[float]:
    return list(np.array(asset_return, dtype=float) - np.array(benchmark_return, dtype=float))
