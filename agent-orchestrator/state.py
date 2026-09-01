"""Shared RunState schema threaded through every node in the graph
(Plan, Locate, Implement, Test, Self-Review, Push). Field names are fixed
by Architecture AD-1 -- do not rename without updating the spine.
"""

from dataclasses import dataclass, field


@dataclass
class RunState:
    run_id: str
    ticket: dict
    plan: str = ""
    file_targets: list = field(default_factory=list)
    diff: str = ""
    test_result: dict = field(default_factory=dict)
    review_verdict: str = ""
    spend_used: float = 0.0
