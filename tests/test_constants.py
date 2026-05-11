from utils.constants import APPLICATION_DIR, CONFIGURATION_DIR, DATA_DIR
from pathlib import Path


class TestConstants:
    def test_application_dir(self):
        assert isinstance(APPLICATION_DIR, Path)
        assert APPLICATION_DIR.is_absolute()

    def test_configuration_dir(self):
        assert isinstance(CONFIGURATION_DIR, Path)
        assert CONFIGURATION_DIR.parent == APPLICATION_DIR
        assert CONFIGURATION_DIR.name == 'config'

    def test_data_dir(self):
        assert isinstance(DATA_DIR, Path)
        assert DATA_DIR.parent == APPLICATION_DIR
        assert DATA_DIR.name == 'data'
