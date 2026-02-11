from __future__ import annotations

from unittest.mock import patch

from graphmind.llm_router import CircuitPhase, CircuitState


class TestCircuitPhaseEnum:
    def test_closed_value(self):
        assert CircuitPhase.CLOSED.value == "closed"

    def test_open_value(self):
        assert CircuitPhase.OPEN.value == "open"

    def test_half_open_value(self):
        assert CircuitPhase.HALF_OPEN.value == "half_open"


class TestCircuitStateInitial:
    def test_starts_closed(self):
        cs = CircuitState()
        assert cs.phase == CircuitPhase.CLOSED

    def test_initial_failures_is_zero(self):
        cs = CircuitState()
        assert cs.failures == 0

    def test_is_available_when_closed(self):
        cs = CircuitState()
        assert cs.is_available is True


class TestCircuitStateFailures:
    def test_single_failure_stays_closed(self):
        cs = CircuitState()
        cs.record_failure()
        assert cs.failures == 1
        assert cs.phase == CircuitPhase.CLOSED

    def test_four_failures_stays_closed(self):
        cs = CircuitState(max_failures=5)
        for _ in range(4):
            cs.record_failure()
        assert cs.failures == 4
        assert cs.phase == CircuitPhase.CLOSED
        assert cs.is_available is True

    def test_five_failures_transitions_to_open(self):
        cs = CircuitState(max_failures=5)
        for _ in range(5):
            cs.record_failure()
        assert cs.failures == 5
        assert cs._phase == CircuitPhase.OPEN
        assert cs.is_available is False

    def test_open_not_available(self):
        cs = CircuitState(max_failures=5)
        for _ in range(5):
            cs.record_failure()
        assert cs.is_available is False

    def test_open_sets_open_until(self):
        cs = CircuitState(max_failures=5)
        for _ in range(5):
            cs.record_failure()
        assert cs.open_until > 0.0


class TestCircuitStateHalfOpen:
    def test_transitions_to_half_open_after_timeout(self):
        cs = CircuitState(max_failures=5)
        for _ in range(5):
            cs.record_failure()
        assert cs._phase == CircuitPhase.OPEN

        # Simulate time passing beyond open_until
        with patch("graphmind.llm_router.time") as mock_time:
            mock_time.monotonic.return_value = cs.open_until + 1.0
            assert cs.phase == CircuitPhase.HALF_OPEN
            assert cs.is_available is True

    def test_still_open_before_timeout(self):
        cs = CircuitState(max_failures=5)
        for _ in range(5):
            cs.record_failure()

        with patch("graphmind.llm_router.time") as mock_time:
            mock_time.monotonic.return_value = cs.open_until - 0.1
            assert cs.phase == CircuitPhase.OPEN
            assert cs.is_available is False


class TestCircuitStateRecovery:
    def test_success_after_half_open_resets_to_closed(self):
        cs = CircuitState(max_failures=5)
        for _ in range(5):
            cs.record_failure()

        # Move time past open_until to trigger HALF_OPEN
        with patch("graphmind.llm_router.time") as mock_time:
            mock_time.monotonic.return_value = cs.open_until + 1.0
            assert cs.phase == CircuitPhase.HALF_OPEN

        # Record success to recover
        cs.record_success()
        assert cs.phase == CircuitPhase.CLOSED
        assert cs.failures == 0
        assert cs.open_until == 0.0
        assert cs.is_available is True

    def test_failure_in_half_open_reopens_circuit(self):
        cs = CircuitState(max_failures=5)
        for _ in range(5):
            cs.record_failure()

        with patch("graphmind.llm_router.time") as mock_time:
            mock_time.monotonic.return_value = cs.open_until + 1.0
            assert cs.phase == CircuitPhase.HALF_OPEN

        # Record failure while HALF_OPEN (failures is already at max_failures=5,
        # so one more record_failure bumps to 6 which is >= max_failures again)
        cs.record_failure()
        assert cs._phase == CircuitPhase.OPEN
        assert cs.is_available is False


class TestCircuitStateCustomMaxFailures:
    def test_custom_max_failures(self):
        cs = CircuitState(max_failures=2)
        cs.record_failure()
        assert cs.phase == CircuitPhase.CLOSED
        cs.record_failure()
        assert cs._phase == CircuitPhase.OPEN

    def test_backoff_grows_exponentially(self):
        cs = CircuitState(max_failures=2)
        cs.record_failure()
        cs.record_failure()
        first_open_until = cs.open_until

        # Record another failure - backoff should increase
        cs.record_failure()
        second_open_until = cs.open_until
        assert second_open_until > first_open_until
