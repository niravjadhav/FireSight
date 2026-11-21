"""Explicit DSA layer for FireSight hotspot investigation.

Uses: adjacency-list graph for proximity links, hash maps for observation
aggregation, and a heap-based priority queue for investigation ordering.
"""
from collections import defaultdict
import heapq
from typing import Any, Dict, List
from src.active_fire import ActiveFireDetector


def build_hotspot_graph(clusters: List[Dict[str, Any]], link_radius_km: float = 10.0) -> Dict[str, Any]:
    """Build an undirected adjacency-list graph between nearby cluster centers."""
    adjacency = {int(c['cluster_id']): [] for c in clusters}
    edges = []
    for i, left in enumerate(clusters):
        for right in clusters[i + 1:]:
            distance = ActiveFireDetector.haversine_distance(
                float(left['latitude']), float(left['longitude']),
                float(right['latitude']), float(right['longitude']))
            if distance <= link_radius_km:
                a, b = int(left['cluster_id']), int(right['cluster_id'])
                adjacency[a].append(b)
                adjacency[b].append(a)
                edges.append({'from_cluster': a, 'to_cluster': b, 'distance_km': round(distance, 2)})
    return {'adjacency_list': adjacency, 'edges': edges, 'link_radius_km': link_radius_km}


def prioritize_clusters(clusters: List[Dict[str, Any]], assessments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Use a hash map to aggregate scores by cluster and a max-heap for ranking."""
    score_by_coordinate = {}
    for item in assessments:
        hotspot = item.get('hotspot', {})
        assessment = item.get('assessment', {})
        try:
            key = (round(float(hotspot['latitude']), 5), round(float(hotspot['longitude']), 5))
            score_by_coordinate[key] = max(float(assessment.get('score', 0)), score_by_coordinate.get(key, 0.0))
        except (KeyError, TypeError, ValueError):
            continue
    heap = []
    for cluster in clusters:
        members = cluster.get('records', [])
        scores = []
        for record in members:
            try:
                key = (round(float(record['latitude']), 5), round(float(record['longitude']), 5))
                scores.append(score_by_coordinate.get(key, 0.0))
            except (KeyError, TypeError, ValueError):
                pass
        mean_score = sum(scores) / len(scores) if scores else 0.0
        # Combined transparent rank: mean contextual score + persistence bonus + size bonus.
        rank_score = mean_score + min(int(cluster.get('persistence_count', 0)), 10) * 2 + min(int(cluster.get('hotspot_count', 0)), 20)
        heapq.heappush(heap, (-rank_score, int(cluster['cluster_id']), mean_score))
    ordered = []
    while heap:
        negative_rank, cluster_id, mean_score = heapq.heappop(heap)
        ordered.append({'cluster_id': cluster_id, 'rank_score': round(-negative_rank, 2),
                        'mean_context_score': round(mean_score, 2), 'queue_position': len(ordered) + 1})
    return ordered


def summarize_graph(graph: Dict[str, Any]) -> Dict[str, int]:
    """Return graph size and degree summary; adjacency list is the graph representation."""
    adjacency = graph.get('adjacency_list', {})
    degrees = [len(neighbors) for neighbors in adjacency.values()]
    return {'nodes': len(adjacency), 'edges': len(graph.get('edges', [])),
            'max_degree': max(degrees, default=0)}
