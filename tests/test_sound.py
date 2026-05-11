from unittest.mock import patch, MagicMock
import subprocess
import pytest

from utils.sound import Sound, SoundFolder, verify_sound, get_all_sounds
from utils.config_definitions import VerificationResult


@pytest.fixture(autouse=True)
def _patch_sound_init_deps():
    """Prevent observer threads and real subprocess in Sound/SoundFolder init."""
    with patch('watchdog.observers.Observer') as mock_obs:
        mock_obs.return_value.is_alive.return_value = False
        mock_obs.return_value.name = 'MockedObserver'
        with patch.object(Sound, '_parse_config'):
            yield


def _make_sound():
    with patch.object(Sound, '_get_player_command', return_value='mpg123'):
        return Sound()


@pytest.fixture
def sound():
    return _make_sound()


class TestRunCmd:
    def test_runs_subprocess(self, sound):
        with patch('utils.sound.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ''
            mock_result.stderr = ''
            mock_run.return_value = mock_result

            sound._run_cmd(['echo', 'hello'])

            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            assert args[0] == ['echo', 'hello']

    def test_raises_on_nonzero_returncode(self, sound):
        with patch('utils.sound.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.check_returncode.side_effect = subprocess.CalledProcessError(1, ['cmd'])
            mock_run.return_value = mock_result

            with pytest.raises(subprocess.CalledProcessError):
                sound._run_cmd(['cmd'])

    def test_passes_startupinfo(self, sound):
        with patch('utils.sound.subprocess.STARTUPINFO') as mock_si, \
             patch('utils.sound.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ''
            mock_result.stderr = ''
            mock_run.return_value = mock_result

            sound._run_cmd(['cmd'])

            mock_si.assert_called_once()
            args, kwargs = mock_run.call_args
            assert 'startupinfo' in kwargs


class TestGetPlayerCommand:
    def test_returns_mpg123_when_found(self):
        sound = _make_sound()
        with patch.object(sound, '_run_cmd') as mock_run:
            cmd = sound._get_player_command()
            assert cmd == 'mpg123'
            mock_run.assert_called_once_with(['mpg123', '--version'])

    def test_falls_back_to_relative_path(self):
        sound = _make_sound()
        with patch.object(sound, '_run_cmd') as mock_run:
            mock_run.side_effect = [
                FileNotFoundError('mpg123 not found'),
                None,
            ]
            cmd = sound._get_player_command()
            assert cmd == '../mpg123/win/mpg123'
            assert mock_run.call_count == 2

    def test_falls_back_on_called_process_error(self):
        sound = _make_sound()
        with patch.object(sound, '_run_cmd') as mock_run:
            mock_run.side_effect = [
                subprocess.CalledProcessError(1, ['mpg123', '--version']),
                None,
            ]
            cmd = sound._get_player_command()
            assert cmd == '../mpg123/win/mpg123'
            assert mock_run.call_count == 2

    def test_raises_when_not_found_anywhere(self):
        sound = _make_sound()
        with patch.object(sound, '_run_cmd') as mock_run:
            mock_run.side_effect = FileNotFoundError('not found')
            with pytest.raises(FileNotFoundError, match='Unable to locate the mpg123 binary'):
                sound._get_player_command()


class TestPlaySound:
    def test_plays_sound_when_enabled(self, sound):
        with patch('utils.sound.os.path.exists', return_value=True), \
             patch.object(sound, '_run_cmd') as mock_run:
            with patch.object(sound, 'sound_enabled', True):
                sound.play_sound('test.mp3')

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert any('test.mp3' in a for a in args)

    def test_does_not_play_when_disabled(self, sound):
        with patch.object(sound, '_run_cmd') as mock_run:
            with patch.object(sound, 'sound_enabled', False):
                sound.play_sound('test.mp3', override=False)
            mock_run.assert_not_called()

    def test_plays_when_disabled_but_override(self, sound):
        with patch('utils.sound.os.path.exists', return_value=True), \
             patch.object(sound, '_run_cmd') as mock_run:
            with patch.object(sound, 'sound_enabled', False):
                sound.play_sound('test.mp3', override=True)
            mock_run.assert_called_once()

    def test_falls_back_to_ding_when_file_missing(self, sound):
        with patch('utils.sound.os.path.exists', side_effect=lambda p: 'ding.mp3' in str(p)), \
             patch.object(sound, '_run_cmd') as mock_run:
            with patch.object(sound, 'sound_enabled', True):
                sound.play_sound('missing.mp3')
            args = mock_run.call_args[0][0]
            assert any('ding.mp3' in a for a in args)

    def test_quiet_flag_in_command(self, sound):
        with patch('utils.sound.os.path.exists', return_value=True), \
             patch.object(sound, '_run_cmd') as mock_run:
            with patch.object(sound, 'sound_enabled', True):
                sound.play_sound('test.mp3')
            args = mock_run.call_args[0][0]
            assert '-q' in args


class TestPlaySoundLang:
    def test_plays_with_lang_prefix(self, sound):
        with patch('utils.sound.os.path.exists', return_value=True), \
             patch.object(sound, '_run_cmd') as mock_run:
            with patch.object(sound, 'sound_enabled', True):
                sound.play_sound_lang('hello.mp3', 'en')

            args = mock_run.call_args[0][0]
            assert any('en' in a and 'hello.mp3' in a for a in args)

    def test_falls_back_to_default_language_when_none(self, sound):
        with patch('utils.sound.os.path.exists', return_value=True), \
             patch.object(sound, '_run_cmd') as mock_run:
            with patch.object(sound, 'sound_enabled', True):
                with patch.object(sound, 'default_language', 'sv'):
                    sound.play_sound_lang('hello.mp3', None)

            args = mock_run.call_args[0][0]
            assert any('sv' in a and 'hello.mp3' in a for a in args)


class TestPlaySoundDefaultLang:
    def test_plays_with_default_language(self, sound):
        with patch('utils.sound.os.path.exists', return_value=True), \
             patch.object(sound, '_run_cmd') as mock_run:
            with patch.object(sound, 'sound_enabled', True):
                with patch.object(sound, 'default_language', 'de'):
                    sound.play_sound_default_lang('hello.mp3')

            args = mock_run.call_args[0][0]
            assert any('de' in a and 'hello.mp3' in a for a in args)


class TestVerifySound:
    def test_returns_true_when_play_succeeds(self, tmp_path):
        sound_file = tmp_path / 'test.mp3'
        sound_file.write_text('')
        with patch('utils.sound.SoundFolder') as mock_folder_cls:
            mock_folder_cls.return_value.get_sounds_dir.return_value = tmp_path
            with patch('utils.sound.Sound.play') as mock_play:
                assert verify_sound('test.mp3') is True
                mock_play.assert_called_once_with('test.mp3', True)

    def test_returns_false_when_play_raises(self, tmp_path):
        sound_file = tmp_path / 'test.mp3'
        sound_file.write_text('')
        with patch('utils.sound.SoundFolder') as mock_folder_cls:
            mock_folder_cls.return_value.get_sounds_dir.return_value = tmp_path
            with patch('utils.sound.Sound.play', side_effect=Exception('fail')):
                assert verify_sound('test.mp3') is False

    def test_returns_verification_result_when_file_missing(self, tmp_path):
        with patch('utils.sound.SoundFolder') as mock_folder_cls:
            mock_folder_cls.return_value.get_sounds_dir.return_value = tmp_path
            result = verify_sound('missing.mp3')
            assert isinstance(result, VerificationResult)
            assert result.status is False
            assert 'missing.mp3' in result.message


class TestGetAllSounds:
    def test_delegates_to_soundfolder(self):
        with patch.object(SoundFolder, 'get_all_sounds', return_value=['a.mp3', 'b.mp3']):
            result = get_all_sounds()
            assert result == ['a.mp3', 'b.mp3']
