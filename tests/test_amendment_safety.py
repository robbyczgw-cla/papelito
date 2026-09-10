from pathlib import Path

import pytest

from papelito import agent as A
from papelito.match import plan_amendment
from papelito.store import Store

NOTE = 'Kindergarten Sonnenblume\nAusflug am Mittwoch, 09.09.2026.\nBitte 8 Euro bis Montag, 07.09.2026 mitgeben.'
FOLLOWUP = 'Kindergarten Sonnenblume\nNachtrag: Der Ausflug wird auf Donnerstag, 11.09.2026 verschoben.'


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    store = Store(tmp_path / 'test.db')
    monkeypatch.setenv('PAPELITO_OUT', str(tmp_path / 'out'))
    monkeypatch.setattr(A, 'SESSION', {})
    monkeypatch.setattr(A, '_CTX', dict(A._CTX))
    A.configure(store=store, profile={'child_name': 'Mateo', 'parent_name': 'Lucía García', 'language': 'en'}, use_models=False)
    yield store
    store.close()


def ingest(text):
    return A.process_photo('synthetic.png', '2026-09-03', language='en', text=text)


def calendar(case):
    return '\n'.join(a['content'] for a in case['artifacts'] if a['kind'] == 'ics' and a['status'] == 'active')


def test_uncertain_amendment_preserves_confirmed_calendar_until_answer(isolated):
    original = ingest(NOTE)
    changed = ingest(FOLLOWUP)
    assert original['id'] == changed['id']
    pending = next(a for a in changed['actions'] if a['deadline_iso'] == '2026-09-11')
    assert pending['status'] == 'pending' and pending['question'] == 'date'
    assert changed['event_date'] == '2026-09-09'
    assert '20260911' not in calendar(changed)
    assert '20260909' in calendar(changed)
    assert isolated.confirm_action(pending['id'], deadline_iso='2026-09-11')
    assert not isolated.confirm_action(pending['id'], deadline_iso='2026-09-12')
    A.write_ics(case_id=changed['id'])
    confirmed = isolated.get_case(changed['id'])
    attend = [a for a in confirmed['actions'] if a['kind'] == 'attend' and a['status'] == 'active']
    assert len(attend) == 1 and attend[0]['deadline_iso'] == '2026-09-11'
    assert confirmed['event_date'] == '2026-09-11'
    assert '20260911' in calendar(confirmed) and '20260909' not in calendar(confirmed)


def test_rejecting_uncertain_amendment_keeps_old_action(isolated):
    ingest(NOTE)
    case = ingest(FOLLOWUP)
    pending = next(a for a in case['actions'] if a['status'] == 'pending')
    assert isolated.drop_action(pending['id'])
    A.write_ics(case_id=case['id'])
    assert '20260909' in calendar(isolated.get_case(case['id']))


def test_uncertain_cancellation_does_not_supersede_anything():
    old = [{'id': 'a', 'kind': 'attend', 'status': 'active'}]
    plan = plan_amendment(old, [{'kind': 'cancel', 'status': 'pending'}])
    assert plan['keep'] == old and plan['supersede'] == []


@pytest.mark.parametrize('state', ['open', 'replied', 'closed'])
def test_duplicate_keeps_case_status_actions_and_artifacts(isolated, state):
    original = ingest(NOTE)
    if state == 'replied':
        isolated.mark_replied(original['id'])
    elif state == 'closed':
        isolated.close_case(original['id'])
    before = isolated.get_case(original['id'])
    duplicate = ingest(NOTE.replace('\n', '  \n'))
    assert duplicate['id'] == original['id'] and duplicate['duplicate']
    assert len(isolated.list_cases()) == 1
    assert isolated.get_case(original['id']) == before


def test_duplicate_upload_discards_only_new_unreferenced_photo(isolated, tmp_path, monkeypatch):
    import web.pipeline as pipeline
    ingest(NOTE)
    original_photo = tmp_path / 'original.png'
    original_photo.write_bytes(b'synthetic')
    new_photo = tmp_path / 'upload.png'
    new_photo.write_bytes(b'synthetic')
    monkeypatch.setattr(pipeline, 'PHOTO_DIR', tmp_path)
    monkeypatch.setattr('web.store.get_store', lambda: type('Adapter', (), {'list_all': lambda self: isolated.list_cases()})())
    monkeypatch.setattr(pipeline, '_core_reader', lambda: lambda *args, **kw: ingest(NOTE))
    result = pipeline.analyse(new_photo, '2026-09-03', 'en')
    assert result['saved'] and not new_photo.exists()
    assert original_photo.exists()
