"""Hardware abstraction layer.

Everything above this package talks to the interfaces in ``base``. The default
runtime has no connected robot devices. The ``pi`` backend imports Pi-only
libraries lazily. Simulation helpers are explicit test fixtures, never a runtime
backend.
"""
