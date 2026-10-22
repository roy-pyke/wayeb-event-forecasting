#!/usr/bin/env python3
"""Run an author service with a bounded Kafka poll default.

The author services call poll() without a timeout in tight loops. Giving the
network client a small wait prevents busy spinning and allows pending broker
metadata/offset operations to make progress. Explicit timeouts remain intact.
No service decisions, forecasting code or message contents are modified.
"""
import runpy
import sys
import faulthandler
import signal
from pathlib import Path

import kafka

ROOT = Path(__file__).resolve().parents[1]
AUTHOR = ROOT / "upstream/rtcef"
if hasattr(signal, "SIGUSR1"):
    # Optional local diagnosis without attaching a debugger or editing author code.
    faulthandler.register(signal.SIGUSR1)
original_poll = kafka.KafkaConsumer.poll


def bounded_poll(self, timeout_ms=50, max_records=None, update_offsets=True):
    return original_poll(self, timeout_ms=timeout_ms, max_records=max_records, update_offsets=update_offsets)


kafka.KafkaConsumer.poll = bounded_poll
sys.path.insert(0, str(AUTHOR))
runpy.run_path(str(AUTHOR / "main.py"), run_name="__main__")

