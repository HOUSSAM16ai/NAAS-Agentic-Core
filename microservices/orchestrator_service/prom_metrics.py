"""
Prometheus metrics for ${skill}.
"""
from prometheus_client import CollectorRegistry, generate_latest

REGISTRY = CollectorRegistry()
