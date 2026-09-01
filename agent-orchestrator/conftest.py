# Empty on purpose: its presence makes pytest insert agent-orchestrator/
# onto sys.path during collection, matching the flat, non-package layout
# every module here uses (bare `from spend_ledger import ...` style
# imports, since orchestrator.py will be the real entry point later and
# Python auto-adds its own script directory to sys.path the same way).
