"""Uncertain model advice must never reach the SMS transport."""
from app.nightly import _send_sms_advisories


def test_uncertain_advisory_is_not_sent(monkeypatch):
    from app.sms import gateway

    class Result:
        def fetchall(self):
            return [('36001', '+15550000000')]

        def fetchone(self):
            return ({'advice_uncertain': True, 'decision': 'IRRIGATE'},)

    class Session:
        def execute(self, *_args, **_kwargs):
            return Result()

    def forbidden(*_args, **_kwargs):
        raise AssertionError('Uncertain advice reached SMS transport')

    monkeypatch.setattr(gateway, 'send_sms', forbidden)
    assert _send_sms_advisories(Session(), '2026-09-09')['sms_sent'] == 0
