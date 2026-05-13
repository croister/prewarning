from unittest.mock import patch

from utils.version import (
    __version__,
    _compute_version,
    _get_commit_sha,
    _get_package_version,
)


class TestGetPackageVersion:
    def test_returns_string(self):
        version = _get_package_version()
        assert isinstance(version, str)
        assert version

    @patch('utils.version._metadata_version')
    def test_normalizes_dev_suffix(self, mock_version):
        mock_version.return_value = '2.2.0.dev42'
        assert _get_package_version() == '2.2.0-dev'

    @patch('utils.version._metadata_version')
    def test_preserves_release_version(self, mock_version):
        mock_version.return_value = '2.2.0'
        assert _get_package_version() == '2.2.0'


class TestGetCommitSha:
    def test_returns_none_without_git_dir(self, tmp_path):
        assert _get_commit_sha(git_dir=tmp_path / '.git') is None

    def test_parses_detached_head(self, tmp_path):
        git_dir = tmp_path / '.git'
        git_dir.mkdir(parents=True)
        git_dir.joinpath('HEAD').write_text('abc1234def567890123456789012345678901234')
        assert _get_commit_sha(git_dir=git_dir) == 'abc1234'

    def test_parses_branch_ref(self, tmp_path):
        git_dir = tmp_path / '.git'
        git_dir.mkdir(parents=True)
        git_dir.joinpath('HEAD').write_text('ref: refs/heads/master\n')
        ref_file = git_dir / 'refs' / 'heads' / 'master'
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text('abc1234def567890123456789012345678901234')
        assert _get_commit_sha(git_dir=git_dir) == 'abc1234'

    def test_returns_none_on_corrupt_head(self, tmp_path):
        git_dir = tmp_path / '.git'
        git_dir.mkdir(parents=True)
        git_dir.joinpath('HEAD').write_text('')
        assert _get_commit_sha(git_dir=git_dir) == ''


class TestComputeVersion:
    @patch('utils.version._get_commit_sha')
    @patch('utils.version._get_package_version')
    def test_appends_sha_for_dev_version(self, mock_pkg_ver, mock_commit):
        mock_pkg_ver.return_value = '2.2.0-dev'
        mock_commit.return_value = 'abc1234'
        assert _compute_version() == '2.2.0-dev+abc1234'

    @patch('utils.version._get_commit_sha')
    @patch('utils.version._get_package_version')
    def test_skips_sha_for_release_version(self, mock_pkg_ver, mock_commit):
        mock_pkg_ver.return_value = '2.2.0'
        mock_commit.return_value = 'abc1234'
        assert _compute_version() == '2.2.0'

    @patch('utils.version._get_commit_sha')
    @patch('utils.version._get_package_version')
    def test_skips_sha_when_no_commit(self, mock_pkg_ver, mock_commit):
        mock_pkg_ver.return_value = '2.2.0-dev'
        mock_commit.return_value = None
        assert _compute_version() == '2.2.0-dev'

    @patch('utils.version._get_commit_sha')
    @patch('utils.version._get_package_version')
    def test_skips_sha_when_already_has_plus(self, mock_pkg_ver, mock_commit):
        mock_pkg_ver.return_value = '2.2.0-dev'
        mock_commit.return_value = 'abc1234'
        _compute_version()
        mock_pkg_ver.return_value = '2.2.0-dev+other'
        assert _compute_version() == '2.2.0-dev+other'


class TestVersionModule:
    def test_version_is_non_empty_string(self):
        assert isinstance(__version__, str)
        assert __version__
