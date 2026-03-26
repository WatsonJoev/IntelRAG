from core.health import check_all


def test_check_all_returns_dict():
    status = check_all()
    assert isinstance(status, dict)
    assert set(status.keys()) == {"vector_store", "metadata_db", "cache", "openrouter"}


def test_metadata_db_healthy():
    status = check_all()
    assert status["metadata_db"] is True


def test_cache_healthy():
    status = check_all()
    assert status["cache"] is True
