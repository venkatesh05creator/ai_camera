"""Vision pipeline: motion gate -> person count -> face-blurred snapshots.

Deterministic parts are pure functions over frames; detectors are injectable
so tests never need a real camera or model files.
"""
