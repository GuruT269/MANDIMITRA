"""Tiny thread-safe single-flight memo cache with TTL (concurrent callers share one computation)."""
import threading
import time
from concurrent.futures import Future

_lock = threading.Lock()
_store = {}


def memo(key, fn, ttl=1800, err_ttl=90):
    owner = False
    with _lock:
        e = _store.get(key)
        if e and (not e["fut"].done() or time.time() - e["t"] < e["ttl"]):
            fut = e["fut"]
        else:
            fut = Future()
            _store[key] = {"fut": fut, "t": time.time(), "ttl": ttl}
            owner = True
    if owner:
        t0 = time.time()
        try:
            res = fn()
            fut.set_result((res, round(time.time() - t0, 2)))
        except Exception as ex:  # cache failures briefly
            fut.set_exception(ex)
            _store[key]["ttl"] = err_ttl
        _store[key]["t"] = time.time()
    res, took = fut.result()
    return res, took, not owner


def peek(key):
    e = _store.get(key)
    if e and e["fut"].done() and not e["fut"].exception():
        return e["fut"].result()[0]
    return None
