from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChartAnnotation:
    x: str
    y: float
    text: str
    kind: str = "callout"


def build_default_annotations(current: float, resistance: float, support: tuple[float, float]) -> list[ChartAnnotation]:
    return [
        ChartAnnotation(x="peak", y=resistance, text="Resistance / breakout confirmation level"),
        ChartAnnotation(x="last", y=current, text="Current price near event-risk zone"),
        ChartAnnotation(x="support", y=sum(support) / 2, text="Support zone; loss would weaken setup"),
    ]
