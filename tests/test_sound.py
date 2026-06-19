from unittest.mock import patch
import pytest

from utils.sound import (
    Sound,
    SoundFolder,
    verify_sound,
    get_all_sounds,
)
from utils.config_definitions import VerificationResult


@pytest.fixture(autouse=True)
def _patch_sound_init_deps():
    """Prevent observer threads in Sound/SoundFolder init."""
    with patch("watchdog.observers.Observer") as mock_obs:
        mock_obs.return_value.is_alive.return_value = False
        mock_obs.return_value.name = "MockedObserver"
        with patch.object(Sound, "_parse_config"):
            yield


def _make_sound():
    return Sound()


@pytest.fixture
def sound():
    return _make_sound()


class TestPlaySound:
    def test_plays_sound_when_enabled(self, sound):
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(sound, "_play_audio") as mock_play,
        ):
            with patch.object(sound, "sound_enabled", True):
                sound.play_sound("test.mp3")

            mock_play.assert_called_once()
            assert "test.mp3" in mock_play.call_args[0][0]

    def test_does_not_play_when_disabled(self, sound):
        with patch.object(sound, "_play_audio") as mock_play:
            with patch.object(sound, "sound_enabled", False):
                sound.play_sound("test.mp3", override=False)
            mock_play.assert_not_called()

    def test_plays_when_disabled_but_override(self, sound):
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(sound, "_play_audio") as mock_play,
        ):
            with patch.object(sound, "sound_enabled", False):
                sound.play_sound("test.mp3", override=True)
            mock_play.assert_called_once()

    def test_falls_back_to_ding_when_file_missing(self, sound):
        with (
            patch(
                "utils.sound.os.path.exists", side_effect=lambda p: "ding.mp3" in str(p)
            ),
            patch.object(sound, "_play_audio") as mock_play,
        ):
            with patch.object(sound, "sound_enabled", True):
                sound.play_sound("missing.mp3")
            assert "ding.mp3" in mock_play.call_args[0][0]


class TestPlayVoice:
    def test_plays_with_voice_prefix(self, sound):
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(sound, "_play_audio") as mock_play,
        ):
            with patch.object(sound, "sound_enabled", True):
                sound.play_voice_sound("hello.mp3", "en-voice")

            path = mock_play.call_args[0][0]
            assert "en-voice" in path and "hello.mp3" in path

    def test_plays_without_prefix_when_voice_none(self, sound):
        sound.default_voice = ""
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(sound, "_play_audio") as mock_play,
        ):
            with patch.object(sound, "sound_enabled", True):
                sound.play_voice_sound("hello.mp3", None)

            path = mock_play.call_args[0][0]
            assert "hello.mp3" in path

    def test_voice_none_falls_back_to_default_voice(self, sound):
        sound.default_voice = "sv-SE-ExampleVoice"
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(sound, "_play_audio") as mock_play,
        ):
            with patch.object(sound, "sound_enabled", True):
                sound.play_voice_sound("hello.mp3", None)

            path = mock_play.call_args[0][0]
            assert "sv-SE-ExampleVoice" in path and "hello.mp3" in path


class TestPlayFile:
    def test_plays_file_when_enabled(self, sound):
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(sound, "_play_audio") as mock_play,
        ):
            with patch.object(sound, "sound_enabled", True):
                sound.play_file_path("some/path/test.mp3")

            mock_play.assert_called_once()
            assert "test.mp3" in mock_play.call_args[0][0]

    def test_does_not_play_when_disabled(self, sound):
        with patch.object(sound, "_play_audio") as mock_play:
            with patch.object(sound, "sound_enabled", False):
                sound.play_file_path("some/path/test.mp3", override=False)
            mock_play.assert_not_called()

    def test_plays_when_disabled_but_override(self, sound):
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(sound, "_play_audio") as mock_play,
        ):
            with patch.object(sound, "sound_enabled", False):
                sound.play_file_path("some/path/test.mp3", override=True)
            mock_play.assert_called_once()

    def test_falls_back_to_ding_when_file_missing(self, sound):
        with (
            patch(
                "utils.sound.os.path.exists",
                side_effect=lambda p: "ding.mp3" in str(p),
            ),
            patch.object(sound, "_play_audio") as mock_play,
        ):
            with patch.object(sound, "sound_enabled", True):
                sound.play_file_path("missing.mp3")
            assert "ding.mp3" in mock_play.call_args[0][0]

    def test_classmethod_delegates_to_instance(self):
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(Sound, "_play_audio") as mock_play,
        ):
            Sound.play_file("some/path/test.mp3", override=True)

            mock_play.assert_called_once()
            assert "test.mp3" in mock_play.call_args[0][0]


class TestVerifySound:
    def test_returns_true_when_play_succeeds(self, tmp_path):
        sound_file = tmp_path / "test.mp3"
        sound_file.write_text("")
        with patch("utils.sound.SoundFolder") as mock_folder_cls:
            mock_folder_cls.return_value.get_sounds_dir.return_value = tmp_path
            with patch("utils.sound.Sound.play") as mock_play:
                assert verify_sound("test.mp3") is True
                mock_play.assert_called_once_with("test.mp3", True)

    def test_returns_false_when_play_raises(self, tmp_path):
        sound_file = tmp_path / "test.mp3"
        sound_file.write_text("")
        with patch("utils.sound.SoundFolder") as mock_folder_cls:
            mock_folder_cls.return_value.get_sounds_dir.return_value = tmp_path
            with patch("utils.sound.Sound.play", side_effect=Exception("fail")):
                assert verify_sound("test.mp3") is False

    def test_returns_verification_result_when_file_missing(self, tmp_path):
        with patch("utils.sound.SoundFolder") as mock_folder_cls:
            mock_folder_cls.return_value.get_sounds_dir.return_value = tmp_path
            result = verify_sound("missing.mp3")
            assert isinstance(result, VerificationResult)
            assert result.status is False
            assert "missing.mp3" in result.message


class TestGetAllSounds:
    def test_delegates_to_soundfolder(self):
        with patch.object(
            SoundFolder, "get_all_sounds", return_value=["a.mp3", "b.mp3"]
        ):
            result = get_all_sounds()
            assert result == ["a.mp3", "b.mp3"]


class TestResolveVoice:
    """Tests for Sound.resolve_voice()"""

    def _make_sound_with_voices(
        self, default_country="SWE", default_voice="sv-voice", fallback_voice="en-voice"
    ):
        s = _make_sound()
        s.default_country = default_country
        s.default_voice = default_voice
        s.fallback_voice = fallback_voice
        return s

    def test_matching_country_returns_default_voice(self):
        s = self._make_sound_with_voices()
        assert s.resolve_voice("SWE") == "sv-voice"

    def test_case_insensitive_match(self):
        s = self._make_sound_with_voices()
        assert s.resolve_voice("swe") == "sv-voice"

    def test_mixed_case_match(self):
        s = self._make_sound_with_voices()
        assert s.resolve_voice("Swe") == "sv-voice"

    def test_non_matching_country_returns_fallback_voice(self):
        s = self._make_sound_with_voices()
        assert s.resolve_voice("NOR") == "en-voice"

    def test_none_country_returns_default_voice(self):
        s = self._make_sound_with_voices()
        assert s.resolve_voice(None) == "sv-voice"

    def test_empty_country_returns_default_voice(self):
        s = self._make_sound_with_voices()
        assert s.resolve_voice("") == "sv-voice"

    def test_returns_none_when_default_voice_empty_and_matching(self):
        s = self._make_sound_with_voices(default_voice="")
        assert s.resolve_voice("SWE") is None

    def test_returns_none_when_fallback_voice_empty_and_non_matching(self):
        s = self._make_sound_with_voices(fallback_voice="")
        assert s.resolve_voice("NOR") is None

    def test_matching_with_different_default_country(self):
        s = self._make_sound_with_voices(default_country="NOR")
        assert s.resolve_voice("NOR") == "sv-voice"
        assert s.resolve_voice("SWE") == "en-voice"
