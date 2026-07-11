from utils.health import HealthAction, HealthIssue, HealthMonitor, HealthStatus


class TestHealthMonitor:
    def test_no_checks_returns_ok(self):
        monitor = HealthMonitor()
        status, issues = monitor.evaluate()
        assert status == HealthStatus.OK
        assert issues == []

    def test_check_with_no_issues_returns_ok(self):
        monitor = HealthMonitor()
        monitor.register_check(lambda: [])
        status, issues = monitor.evaluate()
        assert status == HealthStatus.OK
        assert issues == []

    def test_warning_issue_returns_warning_status(self):
        monitor = HealthMonitor()
        monitor.register_check(
            lambda: [HealthIssue("test warning", HealthStatus.WARNING)]
        )
        status, issues = monitor.evaluate()
        assert status == HealthStatus.WARNING
        assert len(issues) == 1
        assert issues[0].message == "test warning"

    def test_error_issue_returns_error_status(self):
        monitor = HealthMonitor()
        monitor.register_check(lambda: [HealthIssue("test error", HealthStatus.ERROR)])
        status, issues = monitor.evaluate()
        assert status == HealthStatus.ERROR
        assert len(issues) == 1

    def test_error_takes_precedence_over_warning(self):
        monitor = HealthMonitor()
        monitor.register_check(lambda: [HealthIssue("warn", HealthStatus.WARNING)])
        monitor.register_check(lambda: [HealthIssue("err", HealthStatus.ERROR)])
        status, issues = monitor.evaluate()
        assert status == HealthStatus.ERROR
        assert len(issues) == 2

    def test_multiple_checks_aggregate_issues(self):
        monitor = HealthMonitor()
        monitor.register_check(lambda: [HealthIssue("issue1", HealthStatus.WARNING)])
        monitor.register_check(
            lambda: [
                HealthIssue("issue2", HealthStatus.WARNING),
                HealthIssue("issue3", HealthStatus.WARNING),
            ]
        )
        status, issues = monitor.evaluate()
        assert status == HealthStatus.WARNING
        assert len(issues) == 3

    def test_get_primary_action_returns_none_when_no_issues(self):
        monitor = HealthMonitor()
        assert monitor.get_primary_action([]) is None

    def test_get_primary_action_returns_first_action(self):
        monitor = HealthMonitor()
        issues = [
            HealthIssue("a", HealthStatus.WARNING, HealthAction.VOICE_MANAGER),
            HealthIssue("b", HealthStatus.WARNING, HealthAction.SETTINGS),
        ]
        assert monitor.get_primary_action(issues) == HealthAction.VOICE_MANAGER

    def test_get_primary_action_prioritizes_error_actions(self):
        monitor = HealthMonitor()
        issues = [
            HealthIssue("warn", HealthStatus.WARNING, HealthAction.VOICE_MANAGER),
            HealthIssue("err", HealthStatus.ERROR, HealthAction.SETTINGS),
        ]
        assert monitor.get_primary_action(issues) == HealthAction.SETTINGS

    def test_get_primary_action_skips_none_actions(self):
        monitor = HealthMonitor()
        issues = [
            HealthIssue("no action", HealthStatus.WARNING, None),
            HealthIssue("has action", HealthStatus.WARNING, HealthAction.SETTINGS),
        ]
        assert monitor.get_primary_action(issues) == HealthAction.SETTINGS

    def test_get_primary_action_returns_none_when_no_actions(self):
        monitor = HealthMonitor()
        issues = [
            HealthIssue("no action", HealthStatus.WARNING, None),
        ]
        assert monitor.get_primary_action(issues) is None
