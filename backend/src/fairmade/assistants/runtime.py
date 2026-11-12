"""Shared admission control for the local single-worker model runtime."""

from threading import BoundedSemaphore

INFERENCE_SLOT = BoundedSemaphore(1)
