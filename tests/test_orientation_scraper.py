import importlib


def test_scraper_module_is_disabled():
    module = importlib.import_module("scraper")

    assert "disabled" in (module.__doc__ or "").lower()
    assert not hasattr(module, "run_orientation_scraper")
    assert not hasattr(module, "discover_orientation_urls")
    assert not hasattr(module, "parse_orientation_article")
