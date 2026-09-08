from __future__ import annotations

import time
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def isolated_photo_references(monkeypatch):
    # No production database may be read or created by cleanup tests.
    monkeypatch.setattr("web.store.get_store", lambda: SimpleNamespace(list_all=lambda: []))


def _job(photo, *, saved=False, case=None):
    return {
        "id": "privacy-job",
        "created": time.time(),
        "state": "running",
        "lang": "en",
        "photo": str(photo),
        "steps": [],
        "case": case,
        "saved": saved,
        "question": "",
        "error": "",
    }


def test_failed_job_discards_upload_without_a_deletable_case(tmp_path, monkeypatch):
    import web.pipeline as pipeline

    private = tmp_path / "private"
    private.mkdir()
    photo = private / "failed.png"
    photo.write_bytes(b"not an image")
    monkeypatch.setattr(pipeline, "PHOTO_DIR", private)
    monkeypatch.setattr(
        pipeline,
        "analyse",
        lambda *_args, **_kwargs: {
            "case": None,
            "saved": False,
            "question": "Take it again?",
        },
    )

    job = _job(photo)
    pipeline._run(job, "2026-09-04")

    assert job["state"] == "done"
    assert not photo.exists()


def test_prune_discards_only_unsaved_managed_uploads(tmp_path, monkeypatch):
    import web.pipeline as pipeline

    private = tmp_path / "private"
    private.mkdir()
    unsaved = private / "unsaved.png"
    saved = private / "saved.png"
    outside = tmp_path / "outside.png"
    for path in (unsaved, saved, outside):
        path.write_bytes(path.name.encode())
    monkeypatch.setattr(pipeline, "PHOTO_DIR", private)
    monkeypatch.setattr(pipeline, "JOB_TTL_SECONDS", 1)

    old = time.time() - 2
    jobs = {
        "unsaved": {**_job(unsaved), "id": "unsaved", "created": old, "state": "done"},
        "saved": {**_job(saved, saved=True), "id": "saved", "created": old, "state": "done"},
        "outside": {**_job(outside), "id": "outside", "created": old, "state": "done"},
    }
    monkeypatch.setattr(pipeline, "_jobs", jobs)

    pipeline._prune()

    assert jobs == {}
    assert not unsaved.exists()
    assert saved.exists()
    assert outside.exists()


def test_mark_saved_updates_the_live_job(tmp_path, monkeypatch):
    import web.pipeline as pipeline

    photo = tmp_path / "photo.png"
    jobs = {"privacy-job": {**_job(photo), "state": "done"}}
    monkeypatch.setattr(pipeline, "_jobs", jobs)

    pipeline.mark_saved("privacy-job")

    assert jobs["privacy-job"]["saved"] is True


def test_discard_preserves_photo_saved_before_reader_failed(tmp_path, monkeypatch):
    import web.pipeline as pipeline

    photo = tmp_path / "retained.png"
    photo.write_bytes(b"synthetic")
    monkeypatch.setattr(pipeline, "PHOTO_DIR", tmp_path)
    case = {"status": "closed", "_raw": {"papers": [{"photo_path": str(photo)}]}}
    monkeypatch.setattr("web.store.get_store", lambda: SimpleNamespace(list_all=lambda: [case]))
    assert pipeline.discard_photo(photo) is False
    assert photo.exists()


def test_discard_preserves_photo_when_ownership_check_fails(tmp_path, monkeypatch):
    import web.pipeline as pipeline

    photo = tmp_path / "retained.png"
    photo.write_bytes(b"synthetic")
    monkeypatch.setattr(pipeline, "PHOTO_DIR", tmp_path)

    def unavailable():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("web.store.get_store", unavailable)
    assert pipeline.discard_photo(photo) is False
    assert photo.exists()
