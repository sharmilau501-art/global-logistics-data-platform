"""Bounded retry behavior, with no real DB or network calls."""
from __future__ import annotations

import pytest

from logistics.warehouse_runner import is_transient, with_retry


def test_retries_temporary_os_error_then_succeeds():
    calls=[]
    sleeps=[]
    def action():
        calls.append('call')
        if len(calls) < 3:
            raise OSError('resource busy')
        return 'finished'
    result=with_retry(action,3,0.5,sleeps.append)
    assert result=='finished'
    assert len(calls)==3
    assert sleeps==[0.5,1.0]


def test_does_not_retry_bad_data():
    calls=[]
    def action():
        calls.append(True)
        raise ValueError('count mismatch')
    with pytest.raises(ValueError,match='count mismatch'):
        with_retry(action, 5, 0, lambda _:None)
    assert len(calls)==1


def test_does_not_retry_missing_input():
    assert not is_transient(FileNotFoundError('missing'))
    assert is_transient(OSError('temporarily unavailable'))
    assert is_transient(RuntimeError('Could not set lock on file'))


def test_bounded_attempts():
    calls=[]
    def action():
        calls.append(True)
        raise OSError('disk busy')
    with pytest.raises(OSError):
        with_retry(action,2,0,lambda _:None)
    assert len(calls)==2


def test_rejects_bad_retry_settings():
    with pytest.raises(ValueError): with_retry(lambda: None,0)
    with pytest.raises(ValueError): with_retry(lambda: None,1,-1)
