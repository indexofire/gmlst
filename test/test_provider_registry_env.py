from __future__ import annotations

import importlib


def test_provider_registry_uses_env_base_urls(monkeypatch) -> None:
    monkeypatch.setenv("GMLST_PUBMLST_BASE_URL", "http://127.0.0.1:8000/api/db")
    monkeypatch.setenv("GMLST_PASTEUR_BASE_URL", "http://127.0.0.1:9000/api/db")

    import gmlst.database.providers as providers

    providers = importlib.reload(providers)
    pubmlst = providers.get_provider("pubmlst")
    pasteur = providers.get_provider("pasteur")

    assert pubmlst._base_url == "http://127.0.0.1:8000/api/db"
    assert pasteur._base_url == "http://127.0.0.1:9000/api/db"

    monkeypatch.delenv("GMLST_PUBMLST_BASE_URL")
    monkeypatch.delenv("GMLST_PASTEUR_BASE_URL")
    importlib.reload(providers)


def test_provider_registry_registers_private_bigsdb_from_env(monkeypatch) -> None:
    monkeypatch.setenv("GMLST_PRIVATE_BIGSDB_URL", "http://127.0.0.1:7000/api/db")
    monkeypatch.setenv("GMLST_PRIVATE_BIGSDB_NAME", "labdb")
    monkeypatch.setenv("GMLST_PRIVATE_BIGSDB_LABEL", "Lab BIGSdb")

    import gmlst.database.providers as providers

    providers = importlib.reload(providers)
    assert "labdb" in providers.AVAILABLE_PROVIDERS
    labdb = providers.get_provider("labdb")
    assert labdb._base_url == "http://127.0.0.1:7000/api/db"
    assert labdb._label == "Lab BIGSdb"

    monkeypatch.delenv("GMLST_PRIVATE_BIGSDB_URL")
    monkeypatch.delenv("GMLST_PRIVATE_BIGSDB_NAME")
    monkeypatch.delenv("GMLST_PRIVATE_BIGSDB_LABEL")
    importlib.reload(providers)
