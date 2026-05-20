from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re

from equity_research_copilot.adapters.news_adapter import NewsItem


@dataclass
class NewsCluster:
    key: str
    items: list[NewsItem]
    similarity: float = 1.0


def cluster_news_items(items: list[NewsItem], threshold: float = 0.68) -> list[NewsCluster]:
    clusters: list[NewsCluster] = []
    vectors: list[Counter[str]] = []
    for item in items:
        exact_key = _exact_key(item)
        vector = _vector(_cluster_text(item))
        if not vector:
            continue
        placed = False
        for idx, cluster in enumerate(clusters):
            if exact_key and exact_key == cluster.key:
                cluster.items.append(item)
                placed = True
                break
            similarity = _cosine(vector, vectors[idx])
            if similarity >= threshold:
                cluster.items.append(item)
                cluster.similarity = round(max(cluster.similarity, similarity), 3)
                vectors[idx].update(vector)
                placed = True
                break
        if not placed:
            clusters.append(NewsCluster(key=exact_key or _signature(item.title), items=[item]))
            vectors.append(vector)
    return clusters


def novelty_score(cluster: NewsCluster, prior_similarity: float = 0.0) -> float:
    duplicate_penalty = min(0.65, max(0, len(cluster.items) - 1) * 0.14)
    similarity_penalty = min(0.3, max(0.0, prior_similarity) * 0.3)
    hash_bonus = 0.08 if any(item.content_hash for item in cluster.items) else 0.0
    return round(max(0.2, min(1.0, 1.0 - duplicate_penalty - similarity_penalty + hash_bonus)), 2)


def _exact_key(item: NewsItem) -> str:
    if item.canonical_url or item.url:
        return re.sub(r"^https?://", "", (item.canonical_url or item.url).casefold()).rstrip("/")
    if item.content_hash:
        return item.content_hash
    return ""


def _cluster_text(item: NewsItem) -> str:
    return f"{item.title} {item.summary} {item.body[:1200]}"


def _signature(text: str) -> str:
    cleaned = re.sub(r"[^0-9a-z가-힣]+", " ", text.casefold())
    tokens = [token for token in cleaned.split() if len(token) > 2]
    return " ".join(tokens[:14])


def _vector(text: str) -> Counter[str]:
    tokens = [token for token in re.findall(r"[0-9a-z가-힣]+", text.casefold()) if len(token) > 2]
    grams = tokens[:80]
    counter: Counter[str] = Counter(grams)
    for first, second in zip(grams, grams[1:]):
        counter[f"{first}_{second}"] += 1
    return counter


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    overlap = set(left) & set(right)
    dot = sum(left[key] * right[key] for key in overlap)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)
