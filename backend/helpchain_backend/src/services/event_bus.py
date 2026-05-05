from __future__ import annotations

from queue import Full, Queue
from threading import Lock
from typing import Any

_SUBSCRIBERS: set[Queue] = set()
_SUBSCRIBERS_LOCK = Lock()
_QUEUE_MAXSIZE = 32


def subscribe() -> Queue:
    subscriber: Queue = Queue(maxsize=_QUEUE_MAXSIZE)
    with _SUBSCRIBERS_LOCK:
        _SUBSCRIBERS.add(subscriber)
    return subscriber


def unsubscribe(subscriber: Queue) -> None:
    with _SUBSCRIBERS_LOCK:
        _SUBSCRIBERS.discard(subscriber)


def publish(event: dict[str, Any]) -> None:
    with _SUBSCRIBERS_LOCK:
        subscribers = list(_SUBSCRIBERS)

    stale_subscribers: list[Queue] = []
    for subscriber in subscribers:
        try:
            subscriber.put_nowait(event)
        except Full:
            stale_subscribers.append(subscriber)

    for stale_subscriber in stale_subscribers:
        unsubscribe(stale_subscriber)
