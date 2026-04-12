import pytest
from src.backend.polygod_graph import run_monte_carlo


def test_monte_carlo_pnl_logic():
    sim = run_monte_carlo({"size": 100}, {"prob": 0.6}, sims=100, seed=42)
    assert sim["win_prob"] > 0  # Should be based on PnL > 0
    assert sim["expected_pnl"] != 0
