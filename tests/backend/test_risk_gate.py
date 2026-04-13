"""Tests for risk gate logic and Kelly criterion in polygod_graph.py."""

import pytest
from unittest.mock import AsyncMock, patch


def test_calculate_kelly_bounds():
    from src.backend.polygod_graph import calculate_kelly

    # Kelly must always be between 0 and 1
    assert calculate_kelly(0.5) >= 0.0
    assert calculate_kelly(0.5) <= 1.0
    assert calculate_kelly(0.99) <= 1.0
    assert calculate_kelly(0.01) >= 0.0


def test_calculate_kelly_zero_edge():
    from src.backend.polygod_graph import calculate_kelly

    # At exactly 50% probability there is no edge — Kelly should be 0
    result = calculate_kelly(0.5)
    assert result == 0.0


def test_calculate_kelly_positive_edge():
    from src.backend.polygod_graph import calculate_kelly

    # Strong probability should yield positive Kelly
    result = calculate_kelly(0.75)
    assert result > 0.0


def test_run_monte_carlo_returns_required_keys():
    from src.backend.polygod_graph import run_monte_carlo

    result = run_monte_carlo({"size": 100}, {"prob": 0.6, "volume": 50000}, sims=500)
    for key in (
        "expected_pnl",
        "win_prob",
        "worst_case",
        "best_case",
        "confidence_95",
        "confidence_5",
        "recommend_size",
    ):
        assert key in result, f"Missing key: {key}"


def test_run_monte_carlo_win_prob_range():
    from src.backend.polygod_graph import run_monte_carlo

    result = run_monte_carlo({"size": 100}, {"prob": 0.6, "volume": 50000}, sims=500)
    assert 0.0 <= result["win_prob"] <= 1.0


def test_run_monte_carlo_reproducible_with_seed():
    from src.backend.polygod_graph import run_monte_carlo

    # Two identical calls should not crash (determinism not guaranteed without seed arg,
    # but the function should be stable across calls)
    r1 = run_monte_carlo({"size": 100}, {"prob": 0.6, "volume": 50000}, sims=200)
    r2 = run_monte_carlo({"size": 100}, {"prob": 0.6, "volume": 50000}, sims=200)
    # Both should return valid structure
    assert "win_prob" in r1 and "win_prob" in r2


@pytest.mark.asyncio
async def test_execute_node_paper_mode_does_not_call_place_order():
    from src.backend.polygod_graph import execute_node

    state = {
        "mode": 1,
        "market_id": "test-market",
        "verdict": "BUY YES",
        "confidence": 95.0,
        "kelly_fraction": 0.25,
        "kelly_size": 100.0,
        "paper_pnl": 0.0,
        "decision": {"order": {"size": 100}},
        "execution_result": None,
        "debate_history": [],
        "run_id": "test-run",
        "market_data": {},
        "question": "Test?",
        "statistics": "",
        "time_decay": "",
        "generalist": "",
        "macro": "",
        "devil": "",
        "debate_round": 1,
        "simulation": None,
        "risk_status": "low",
        "on_chain_fills": [],
        "whale_context": "",
        "final_decision": None,
    }
    with patch(
        "src.backend.polygod_graph.polymarket_client.place_order",
        new_callable=AsyncMock,
    ) as mock_place:
        result_state = await execute_node(state)
        mock_place.assert_not_called()
        assert result_state["execution_result"] is not None
