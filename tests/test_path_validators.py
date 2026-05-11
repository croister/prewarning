import tempfile
from pathlib import Path

from validators.path_validators import is_path, path_exists, file_exists, directory_exists


class TestIsPath:
    def test_valid_absolute_path(self):
        assert is_path(str(Path.home())) is True

    def test_valid_path_object(self):
        assert is_path(Path.home()) is True

    def test_empty_returns_true(self):
        assert is_path('') is True


class TestPathExists:
    def test_existing_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert path_exists(tmp) is True

    def test_non_existing(self):
        from validators.validation_error import ValidationError
        result = path_exists('/nonexistent/path/12345')
        assert isinstance(result, ValidationError)


class TestFileExists:
    def test_existing_file(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
            f.write(b'hello')
            tmp_path = f.name
        try:
            assert file_exists(tmp_path) is True
        finally:
            Path(tmp_path).unlink()

    def test_directory_is_not_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            from validators.validation_error import ValidationError
            result = file_exists(tmp)
            assert isinstance(result, ValidationError)

    def test_non_existing(self):
        result = file_exists('/nonexistent/file.txt')
        assert not result


class TestDirectoryExists:
    def test_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert directory_exists(tmp) is True

    def test_file_is_not_directory(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
            f.write(b'hello')
            tmp_path = f.name
        try:
            from validators.validation_error import ValidationError
            result = directory_exists(tmp_path)
            assert isinstance(result, ValidationError)
        finally:
            Path(tmp_path).unlink()

    def test_non_existing(self):
        result = directory_exists('/nonexistent/dir')
        assert not result
