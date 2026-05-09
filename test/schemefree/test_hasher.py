"""Tests for schemefree hasher strategies."""

import pytest

from gmlst.schemefree.hasher import (
    BlastHashStrategy,
    HashStrategyManager,
    SafeHashStrategy,
    StrictHashStrategy,
)


class TestSafeHashStrategy:
    """Test safe hashing strategy (MD5 + verification)."""

    def test_basic_allele_assignment(self):
        """Test basic allele ID assignment."""
        hasher = SafeHashStrategy()

        # First sequence
        allele1 = hasher.get_allele_id("ATCGATCGATCG", "locus_1")
        assert allele1 == "locus_1_1"

        # Same sequence should get same ID
        allele2 = hasher.get_allele_id("ATCGATCGATCG", "locus_1")
        assert allele2 == "locus_1_1"

        stats = hasher.get_stats()
        assert stats["total_sequences"] == 2
        assert stats["unique_alleles"] == 1

    def test_different_sequences_get_different_ids(self):
        """Test that different sequences get different allele IDs."""
        hasher = SafeHashStrategy()

        allele1 = hasher.get_allele_id("ATCGATCGATCG", "locus_1")
        allele2 = hasher.get_allele_id("ATCGATCGATCC", "locus_1")  # One base different

        assert allele1 == "locus_1_1"
        assert allele2 == "locus_1_2"

        stats = hasher.get_stats()
        assert stats["unique_alleles"] == 2

    def test_sequence_normalization(self):
        """Test that sequences are normalized (case, gaps)."""
        hasher = SafeHashStrategy()

        # Should be treated as same sequence
        allele1 = hasher.get_allele_id("ATCG", "locus_1")
        allele2 = hasher.get_allele_id("atcg", "locus_1")
        allele3 = hasher.get_allele_id("A-T-C-G", "locus_1")

        assert allele1 == allele2 == allele3 == "locus_1_1"

    def test_different_loci(self):
        """Test that different loci have independent numbering."""
        hasher = SafeHashStrategy()

        hasher.get_allele_id("ATCG", "locus_1")
        hasher.get_allele_id("GGGG", "locus_1")
        allele2 = hasher.get_allele_id("ATCG", "locus_2")

        assert allele2 == "locus_2_1"

    def test_locus_numbering_is_independent_of_global_id_growth(self):
        hasher = SafeHashStrategy()

        for idx in range(1, 6):
            hasher.get_allele_id(f"ATCG{idx}", "locus_1")

        first_other_locus = hasher.get_allele_id("ATCG1", "locus_2")
        second_other_locus = hasher.get_allele_id("TTTT1", "locus_2")

        assert first_other_locus == "locus_2_1"
        assert second_other_locus == "locus_2_2"


class TestStrictHashStrategy:
    """Test strict hashing strategy (SHA-256)."""

    def test_basic_functionality(self):
        """Test basic strict hashing."""
        hasher = StrictHashStrategy()

        allele1 = hasher.get_allele_id("ATCGATCGATCG", "locus_1")
        allele2 = hasher.get_allele_id("ATCGATCGATCG", "locus_1")

        assert allele1 == "locus_1_1"
        assert allele2 == "locus_1_1"

    def test_store_full_sequences(self):
        """Test storing full sequences option."""
        hasher = StrictHashStrategy({"store_full_sequences": True})

        hasher.get_allele_id("ATCGATCGATCG", "locus_1")

        # Check that full sequence is stored
        for allele_info in hasher.allele_db.values():
            assert allele_info["seq"] == "ATCGATCGATCG"


class TestHashStrategyManager:
    """Test hash strategy manager."""

    def test_get_safe_strategy(self):
        """Test getting safe strategy from manager."""
        strategy = HashStrategyManager.get_strategy("safe")
        assert isinstance(strategy, SafeHashStrategy)

    def test_get_strict_strategy(self):
        """Test getting strict strategy from manager."""
        strategy = HashStrategyManager.get_strategy("strict")
        assert isinstance(strategy, StrictHashStrategy)

    def test_list_strategies(self):
        """Test listing available strategies."""
        strategies = HashStrategyManager.list_strategies()
        assert "blast" in strategies
        assert "safe" in strategies
        assert "strict" in strategies

    def test_unknown_strategy_raises_error(self):
        """Test that unknown strategy raises error."""
        with pytest.raises(ValueError, match="Unknown strategy"):
            HashStrategyManager.get_strategy("nonexistent")

    def test_strategy_with_config(self):
        config = {"verification_rate": 0.05}
        strategy = HashStrategyManager.get_strategy("safe", config)
        assert isinstance(strategy, SafeHashStrategy)
        assert strategy.verification_rate == 0.05


class TestFastAndUltraStrategies:
    """Test fast and ultra strategies (require xxhash)."""

    def test_fast_strategy(self):
        """Test fast strategy if xxhash available."""
        try:
            from gmlst.schemefree.hasher import FastHashStrategy

            hasher = FastHashStrategy()

            allele1 = hasher.get_allele_id("ATCGATCGATCG", "locus_1")
            allele2 = hasher.get_allele_id("ATCGATCGATCG", "locus_1")

            assert allele1 == "locus_1_1"
            assert allele2 == "locus_1_1"
        except ImportError:
            pytest.skip("xxhash not installed")

    def test_ultra_strategy(self):
        """Test ultra strategy if xxhash available."""
        try:
            from gmlst.schemefree.hasher import UltraHashStrategy

            hasher = UltraHashStrategy()

            allele1 = hasher.get_allele_id("ATCGATCGATCG", "locus_1")
            allele2 = hasher.get_allele_id("ATCGATCGATCG", "locus_1")

            assert allele1 == "locus_1_1"
            assert allele2 == "locus_1_1"
        except ImportError:
            pytest.skip("xxhash not installed")


class TestStrategyComparison:
    """Compare different strategies."""

    def test_all_strategies_produce_consistent_results(self):
        """Test that all strategies produce consistent allele assignments."""
        sequences = ["ATCG", "ATCG", "TTGC", "ATCG", "GGCC"]

        strategies_to_test = ["safe", "strict"]

        for strategy_name in strategies_to_test:
            hasher = HashStrategyManager.get_strategy(strategy_name)
            results = [hasher.get_allele_id(seq, "test_locus") for seq in sequences]

            # Same sequences should get same IDs
            assert results[0] == results[1] == results[3]
            # Different sequences should get different IDs
            assert results[0] != results[2]
            assert results[0] != results[4]


class TestBlastHashStrategy:
    def test_exact_sequence_reuse(self, monkeypatch):
        import gmlst.schemefree.hasher as hasher_module

        monkeypatch.setattr(hasher_module.shutil, "which", lambda _: "/usr/bin/tool")

        hasher = BlastHashStrategy()
        allele1 = hasher.get_allele_id("ATCGATCG", "locus_1")
        allele2 = hasher.get_allele_id("ATCGATCG", "locus_1")

        assert allele1 == "locus_1_1"
        assert allele2 == "locus_1_1"
        assert hasher.get_stats()["total_sequences"] == 2

    def test_blast_match_reuses_existing_allele(self, monkeypatch):
        import gmlst.schemefree.hasher as hasher_module

        monkeypatch.setattr(hasher_module.shutil, "which", lambda _: "/usr/bin/tool")

        hasher = BlastHashStrategy()
        hasher.get_allele_id("ATCGATCG", "locus_1")

        monkeypatch.setattr(hasher, "_find_by_blast", lambda _: 1)
        allele2 = hasher.get_allele_id("ATCGATCA", "locus_1")

        assert allele2 == "locus_1_1"
        assert hasher.get_stats()["unique_alleles"] == 1

    def test_no_blast_match_creates_new_allele(self, monkeypatch):
        import gmlst.schemefree.hasher as hasher_module

        monkeypatch.setattr(hasher_module.shutil, "which", lambda _: "/usr/bin/tool")

        hasher = BlastHashStrategy()
        hasher.get_allele_id("ATCGATCG", "locus_1")
        monkeypatch.setattr(hasher, "_find_by_blast", lambda _: None)

        allele2 = hasher.get_allele_id("GGGGCCCC", "locus_1")
        assert allele2 == "locus_1_2"
        assert hasher.get_stats()["unique_alleles"] == 2
