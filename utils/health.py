"""Application health monitoring."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, unique


@unique
class HealthStatus(Enum):
    """Overall health status levels."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


@unique
class HealthAction(Enum):
    """Action to take when the user clicks the health indicator."""

    VOICE_MANAGER = "voice_manager"
    SETTINGS = "settings"


@dataclass
class HealthIssue:
    """A single health issue reported by a check."""

    message: str
    status: HealthStatus
    action: HealthAction | None = None


class HealthMonitor:
    """Evaluates registered health checks and reports overall status."""

    def __init__(self):
        self._checks: list[Callable[[], list[HealthIssue]]] = []

    def register_check(self, check: Callable[[], list[HealthIssue]]) -> None:
        """Register a health check function."""
        self._checks.append(check)

    def evaluate(self) -> tuple[HealthStatus, list[HealthIssue]]:
        """Run all checks and return the worst status + all issues."""
        all_issues: list[HealthIssue] = []
        for check in self._checks:
            issues = check()
            all_issues.extend(issues)

        if not all_issues:
            return HealthStatus.OK, []

        worst = HealthStatus.OK
        for issue in all_issues:
            if issue.status == HealthStatus.ERROR:
                worst = HealthStatus.ERROR
                break
            elif issue.status == HealthStatus.WARNING:
                worst = HealthStatus.WARNING

        return worst, all_issues

    def get_primary_action(self, issues: list[HealthIssue]) -> HealthAction | None:
        """Return the most relevant action for the current issues."""
        if not issues:
            return None
        # Prioritize errors over warnings
        error_issues = [i for i in issues if i.status == HealthStatus.ERROR]
        target = error_issues if error_issues else issues
        # Return the first action found
        for issue in target:
            if issue.action is not None:
                return issue.action
        return None
