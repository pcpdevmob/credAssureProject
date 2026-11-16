#!/bin/sh
# Minimal demo reset (Phase 12 adds the replay cache): see scripts/demo_reset.py.
cd "$(dirname "$0")/../.." && exec make demo-reset
