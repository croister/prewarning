import os
from unittest.mock import patch, MagicMock
import subprocess
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
    """Prevent observer threads and real subprocess in Sound/SoundFolder init."""
    with patch("watchdog.observers.Observer") as mock_obs:
        mock_obs.return_value.is_alive.return_value = False
        mock_obs.return_value.name = "MockedObserver"
        with patch.object(Sound, "_parse_config"):
            yield


def _make_sound():
    with patch.object(Sound, "_get_player_command", return_value="mpg123"):
        return Sound()


@pytest.fixture
def sound():
    return _make_sound()


class TestRunCmd:
    def test_runs_subprocess(self, sound):
        with patch("utils.sound.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            sound._run_cmd(["echo", "hello"])

            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            assert args[0] == ["echo", "hello"]

    def test_raises_on_nonzero_returncode(self, sound):
        with patch("utils.sound.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.check_returncode.side_effect = subprocess.CalledProcessError(
                1, ["cmd"]
            )
            mock_run.return_value = mock_result

            with pytest.raises(subprocess.CalledProcessError):
                sound._run_cmd(["cmd"])

    @pytest.mark.skipif(os.name != "nt", reason="STARTUPINFO is Windows-only")
    def test_passes_startupinfo(self, sound):
        with (
            patch("utils.sound.subprocess.STARTUPINFO") as mock_si,
            patch("utils.sound.run") as mock_run,
        ):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            sound._run_cmd(["cmd"])

            mock_si.assert_called_once()
            args, kwargs = mock_run.call_args
            assert "startupinfo" in kwargs


class TestGetPlayerCommand:
    def test_returns_mpg123_when_found(self):
        sound = _make_sound()
        with patch.object(sound, "_run_cmd") as mock_run:
            cmd = sound._get_player_command()
            assert cmd == "mpg123"
            mock_run.assert_called_once_with(["mpg123", "--version"])

    def test_falls_back_to_relative_path(self):
        sound = _make_sound()
        from pathlib import Path

        expected = str(Path(__file__).resolve().parent.parent / "mpg123/win/mpg123")
        with patch.object(sound, "_run_cmd") as mock_run:
            mock_run.side_effect = [
                FileNotFoundError("mpg123 not found"),
                None,
            ]
            cmd = sound._get_player_command()
            assert cmd == expected
            assert mock_run.call_count == 2

    def test_falls_back_on_called_process_error(self):
        sound = _make_sound()
        from pathlib import Path

        expected = str(Path(__file__).resolve().parent.parent / "mpg123/win/mpg123")
        with patch.object(sound, "_run_cmd") as mock_run:
            mock_run.side_effect = [
                subprocess.CalledProcessError(1, ["mpg123", "--version"]),
                None,
            ]
            cmd = sound._get_player_command()
            assert cmd == expected
            assert mock_run.call_count == 2

    def test_raises_when_not_found_anywhere(self):
        sound = _make_sound()
        with patch.object(sound, "_run_cmd") as mock_run:
            mock_run.side_effect = FileNotFoundError("not found")
            with pytest.raises(
                FileNotFoundError, match="Unable to locate the mpg123 binary"
            ):
                sound._get_player_command()


class TestPlaySound:
    def test_plays_sound_when_enabled(self, sound):
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(sound, "_run_cmd") as mock_run,
        ):
            with patch.object(sound, "sound_enabled", True):
                sound.play_sound("test.mp3")

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert any("test.mp3" in a for a in args)

    def test_does_not_play_when_disabled(self, sound):
        with patch.object(sound, "_run_cmd") as mock_run:
            with patch.object(sound, "sound_enabled", False):
                sound.play_sound("test.mp3", override=False)
            mock_run.assert_not_called()

    def test_plays_when_disabled_but_override(self, sound):
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(sound, "_run_cmd") as mock_run,
        ):
            with patch.object(sound, "sound_enabled", False):
                sound.play_sound("test.mp3", override=True)
            mock_run.assert_called_once()

    def test_falls_back_to_ding_when_file_missing(self, sound):
        with (
            patch(
                "utils.sound.os.path.exists", side_effect=lambda p: "ding.mp3" in str(p)
            ),
            patch.object(sound, "_run_cmd") as mock_run,
        ):
            with patch.object(sound, "sound_enabled", True):
                sound.play_sound("missing.mp3")
            args = mock_run.call_args[0][0]
            assert any("ding.mp3" in a for a in args)

    def test_quiet_flag_in_command(self, sound):
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(sound, "_run_cmd") as mock_run,
        ):
            with patch.object(sound, "sound_enabled", True):
                sound.play_sound("test.mp3")
            args = mock_run.call_args[0][0]
            assert "-q" in args


class TestPlayVoice:
    def test_plays_with_voice_prefix(self, sound):
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(sound, "_run_cmd") as mock_run,
        ):
            with patch.object(sound, "sound_enabled", True):
                sound.play_voice_sound("hello.mp3", "en-voice")

            args = mock_run.call_args[0][0]
            assert any("en-voice" in a and "hello.mp3" in a for a in args)

    def test_plays_without_prefix_when_voice_none(self, sound):
        sound.default_voice = ""
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(sound, "_run_cmd") as mock_run,
        ):
            with patch.object(sound, "sound_enabled", True):
                sound.play_voice_sound("hello.mp3", None)

            args = mock_run.call_args[0][0]
            assert any("hello.mp3" in a for a in args)
            assert not any("\\" in a or "//" in a for a in args)

    def test_voice_none_falls_back_to_default_voice(self, sound):
        sound.default_voice = "sv-SE-ExampleVoice"
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(sound, "_run_cmd") as mock_run,
        ):
            with patch.object(sound, "sound_enabled", True):
                sound.play_voice_sound("hello.mp3", None)

            args = mock_run.call_args[0][0]
            assert any("sv-SE-ExampleVoice" in a and "hello.mp3" in a for a in args)


class TestPlayFile:
    def test_plays_file_when_enabled(self, sound):
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(sound, "_run_cmd") as mock_run,
        ):
            with patch.object(sound, "sound_enabled", True):
                sound.play_file_path("some/path/test.mp3")

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert any("test.mp3" in a for a in args)
            assert "-q" in args

    def test_does_not_play_when_disabled(self, sound):
        with patch.object(sound, "_run_cmd") as mock_run:
            with patch.object(sound, "sound_enabled", False):
                sound.play_file_path("some/path/test.mp3", override=False)
            mock_run.assert_not_called()

    def test_plays_when_disabled_but_override(self, sound):
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(sound, "_run_cmd") as mock_run,
        ):
            with patch.object(sound, "sound_enabled", False):
                sound.play_file_path("some/path/test.mp3", override=True)
            mock_run.assert_called_once()

    def test_falls_back_to_ding_when_file_missing(self, sound):
        with (
            patch(
                "utils.sound.os.path.exists",
                side_effect=lambda p: "ding.mp3" in str(p),
            ),
            patch.object(sound, "_run_cmd") as mock_run,
        ):
            with patch.object(sound, "sound_enabled", True):
                sound.play_file_path("missing.mp3")
            args = mock_run.call_args[0][0]
            assert any("ding.mp3" in a for a in args)

    def test_classmethod_delegates_to_instance(self):
        with (
            patch("utils.sound.os.path.exists", return_value=True),
            patch.object(Sound, "_get_player_command", return_value="mpg123"),
            patch.object(Sound, "_run_cmd") as mock_run,
        ):
            Sound.play_file("some/path/test.mp3", override=True)

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert any("test.mp3" in a for a in args)


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
