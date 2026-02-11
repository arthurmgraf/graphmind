from __future__ import annotations

from graphmind.features import FeatureFlag, FeatureFlagRegistry


class TestFeatureFlagRegistry:
    def test_default_flags_exist(self):
        registry = FeatureFlagRegistry()
        flags = registry.list_flags()
        names = {f["name"] for f in flags}
        assert "streaming_enabled" in names
        assert "crewai_enabled" in names
        assert "dedup_enabled" in names
        assert "webhooks_enabled" in names
        assert "multi_tenancy_enabled" in names
        assert "conversation_memory_enabled" in names
        assert "injection_detection_enabled" in names
        assert "chaos_enabled" in names

    def test_default_flags_count(self):
        registry = FeatureFlagRegistry()
        assert len(registry.list_flags()) == 8

    def test_is_active_returns_bool(self):
        registry = FeatureFlagRegistry()
        result = registry.is_active("streaming_enabled")
        assert isinstance(result, bool)

    def test_enabled_flag_is_active(self):
        registry = FeatureFlagRegistry()
        assert registry.is_active("streaming_enabled") is True

    def test_disabled_flag_is_not_active(self):
        registry = FeatureFlagRegistry()
        assert registry.is_active("webhooks_enabled") is False

    def test_unknown_flag_returns_false(self):
        registry = FeatureFlagRegistry()
        assert registry.is_active("nonexistent_flag") is False

    def test_register_new_flag(self):
        registry = FeatureFlagRegistry()
        new_flag = FeatureFlag("my_custom_flag", enabled=True, description="Custom")
        registry.register(new_flag)
        assert registry.is_active("my_custom_flag") is True

    def test_register_overwrites_existing(self):
        registry = FeatureFlagRegistry()
        replacement = FeatureFlag("streaming_enabled", enabled=False)
        registry.register(replacement)
        assert registry.is_active("streaming_enabled") is False

    def test_set_enabled_toggles_flag(self):
        registry = FeatureFlagRegistry()
        assert registry.is_active("streaming_enabled") is True
        registry.set_enabled("streaming_enabled", False)
        assert registry.is_active("streaming_enabled") is False
        registry.set_enabled("streaming_enabled", True)
        assert registry.is_active("streaming_enabled") is True

    def test_list_flags_returns_dicts(self):
        registry = FeatureFlagRegistry()
        flags = registry.list_flags()
        assert isinstance(flags, list)
        for f in flags:
            assert "name" in f
            assert "enabled" in f
            assert "rollout_percentage" in f
            assert "description" in f


class TestFeatureFlagRollout:
    def test_full_rollout_always_active(self):
        flag = FeatureFlag("test", enabled=True, rollout_percentage=100.0)
        # Should always be active regardless of tenant
        for i in range(20):
            assert flag.is_active(f"tenant-{i}") is True

    def test_zero_rollout_never_active_for_tenant(self):
        flag = FeatureFlag("test", enabled=True, rollout_percentage=0.0)
        # With 0% rollout, no deterministic tenant hash can be < 0
        for i in range(20):
            assert flag.is_active(f"tenant-{i}") is False

    def test_disabled_flag_ignores_rollout(self):
        flag = FeatureFlag("test", enabled=False, rollout_percentage=100.0)
        assert flag.is_active() is False
        assert flag.is_active("some-tenant") is False

    def test_percentage_rollout_deterministic_for_same_tenant(self):
        flag = FeatureFlag("test_flag", enabled=True, rollout_percentage=50.0)
        tenant = "tenant-abc"
        first_result = flag.is_active(tenant)
        # Same tenant + same flag name should always produce same result
        for _ in range(10):
            assert flag.is_active(tenant) == first_result

    def test_percentage_rollout_uses_hash(self):
        """Verify the hash-based rollout produces consistent results per tenant."""
        flag = FeatureFlag("rollout_test", enabled=True, rollout_percentage=50.0)
        # Compute expected value from the hash formula
        tenant = "deterministic-tenant"
        seed = hash(f"rollout_test:{tenant}") % 100
        expected = seed < 50.0
        assert flag.is_active(tenant) == expected

    def test_no_tenant_with_partial_rollout_is_nondeterministic(self):
        """Without tenant_id, result depends on random.random()."""
        flag = FeatureFlag("test", enabled=True, rollout_percentage=50.0)
        # We cannot assert a specific value, but we can confirm it returns bool
        result = flag.is_active()
        assert isinstance(result, bool)
