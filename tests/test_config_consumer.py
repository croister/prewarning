from unittest.mock import patch
import pytest

from utils.config_consumer import ConfigConsumer
from utils.config_definitions import ConfigSectionDefinition


class TestConfigConsumer:
    def test_abstract_class(self):
        with pytest.raises(TypeError):
            ConfigConsumer()

    def test_config_section_definition_not_implemented(self):
        class Missing(ConfigConsumer):
            pass

        with pytest.raises(TypeError):
            Missing()

    def test_config_section_definition_classmethod(self):
        with patch("utils.config.Config.register_config_section_listener"):

            class MyConsumer(ConfigConsumer):
                @classmethod
                def config_section_definition(cls):
                    return ConfigSectionDefinition("my_section", "My Section")

                def __init__(self):
                    super().__init__()

            c = MyConsumer()
            assert hasattr(c, "logger")

    @patch("utils.config.Config")
    def test_init_registers_listener(self, mock_config_class):
        section_def = ConfigSectionDefinition("test_section", "Test Section")

        class TestConsumer(ConfigConsumer):
            @classmethod
            def config_section_definition(cls):
                return section_def

            def __init__(self):
                super().__init__()

        c = TestConsumer()
        mock_config_class.register_config_section_listener.assert_called_once_with(
            "test_section", c
        )

    @patch("utils.config.Config")
    def test_get_config_section_definitions_default(self, mock_config_class):
        section_def = ConfigSectionDefinition("sect", "Sect")

        class TestConsumer(ConfigConsumer):
            @classmethod
            def config_section_definition(cls):
                return section_def

            def __init__(self):
                super().__init__()

        c = TestConsumer()
        definitions = c.get_config_section_definitions()
        assert definitions == [section_def]

    @patch("utils.config.Config")
    def test_get_config_section_definitions_override(self, mock_config_class):
        main_def = ConfigSectionDefinition("main", "Main")
        extra_def = ConfigSectionDefinition("extra", "Extra")

        class TestConsumer(ConfigConsumer):
            @classmethod
            def config_section_definition(cls):
                return main_def

            def get_config_section_definitions(self):
                return [main_def, extra_def]

            def __init__(self):
                super().__init__()

        c = TestConsumer()
        assert c.get_config_section_definitions() == [main_def, extra_def]

    @patch("utils.config.Config")
    def test_init_registers_all_definitions(self, mock_config_class):
        main_def = ConfigSectionDefinition("main", "Main")

        class TestConsumer(ConfigConsumer):
            @classmethod
            def config_section_definition(cls):
                return main_def

            def __init__(self):
                super().__init__()

        TestConsumer()
        assert mock_config_class.register_config_section_listener.call_count == 1

    @patch("utils.config.Config")
    def test_config_updated_default_noop(self, mock_config_class):
        class TestConsumer(ConfigConsumer):
            @classmethod
            def config_section_definition(cls):
                return ConfigSectionDefinition("s", "S")

            def __init__(self):
                super().__init__()

        c = TestConsumer()
        result = c.config_updated(["section1"])
        assert result is None

    @patch("utils.config.Config")
    def test_str_repr(self, mock_config_class):
        class TestConsumer(ConfigConsumer):
            @classmethod
            def config_section_definition(cls):
                return ConfigSectionDefinition("s", "S")

            def __init__(self):
                super().__init__()

        c = TestConsumer()
        assert "ConfigConsumer" in repr(c)
        assert "ConfigConsumer" in str(c)

    @patch("utils.config.Config")
    def test_definitions_none_does_not_register(self, mock_config_class):
        class TestConsumer(ConfigConsumer):
            @classmethod
            def config_section_definition(cls):
                return ConfigSectionDefinition("s", "S")

            def get_config_section_definitions(self):
                return None

            def __init__(self):
                super().__init__()

        TestConsumer()
        mock_config_class.register_config_section_listener.assert_not_called()

    @patch("utils.config.Config")
    def test_definitions_empty_list_does_not_register(self, mock_config_class):
        class TestConsumer(ConfigConsumer):
            @classmethod
            def config_section_definition(cls):
                return ConfigSectionDefinition("s", "S")

            def get_config_section_definitions(self):
                return []

            def __init__(self):
                super().__init__()

        TestConsumer()
        mock_config_class.register_config_section_listener.assert_not_called()
