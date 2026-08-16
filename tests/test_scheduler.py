from robots import scheduler as scheduler_module


def test_start_scheduler_does_not_register_orientation_scraper(monkeypatch):
    added_jobs = []

    class DummyScheduler:
        def add_job(self, *args, **kwargs):
            added_jobs.append(kwargs.get("id"))

        def start(self):
            return None

    dummy_scheduler = DummyScheduler()
    monkeypatch.setattr(scheduler_module, "BackgroundScheduler", lambda *args, **kwargs: dummy_scheduler)

    scheduler_module.start_scheduler()

    assert "initial_orientation_scraper" not in added_jobs
    assert "orientation_scraper" not in added_jobs
