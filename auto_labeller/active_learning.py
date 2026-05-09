import math

from .model import Prediction


def entropy(confidences: list[float]) -> float:
    return -sum(c * math.log(c + 1e-10) for c in confidences if c > 0)


def rank_by_uncertainty(
    predictions: list[Prediction], method: str = "least_confident"
) -> list[Prediction]:
    if method == "least_confident":
        return sorted(
            predictions,
            key=lambda p: max(p.confidences) if p.confidences else 0,
        )
    elif method == "entropy":
        return sorted(
            predictions, key=lambda p: entropy(p.confidences), reverse=True
        )
    else:
        raise ValueError(f"Unknown method: {method}")


def select_for_review(
    predictions: list[Prediction],
    n: int | None = None,
    threshold: float | None = None,
) -> list[Prediction]:
    ranked = rank_by_uncertainty(predictions)
    if threshold is not None:
        ranked = [p for p in ranked if max(p.confidences, default=0) < threshold]
    if n is not None:
        ranked = ranked[:n]
    return ranked
