from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.edge_tts import VoiceFile, generate, generate_range, list_voices


@pytest.fixture(autouse=True)
def mock_edge_tts():
    with patch("utils.edge_tts.edge_tts") as mock:
        mock.list_voices = AsyncMock()
        mock_communicate = MagicMock()
        mock_communicate.save = AsyncMock()
        mock.Communicate = MagicMock(return_value=mock_communicate)
        yield mock


class TestListVoices:
    def test_returns_voice_list(self, mock_edge_tts):
        expected = [
            {"ShortName": "sv-SE-SofieNeural", "Gender": "Female", "Locale": "sv-SE"},
            {"ShortName": "en-US-JennyNeural", "Gender": "Female", "Locale": "en-US"},
        ]
        mock_edge_tts.list_voices.return_value = expected

        result = list_voices()

        assert result == expected
        mock_edge_tts.list_voices.assert_awaited_once()

    def test_returns_empty_list_on_error(self, mock_edge_tts):
        mock_edge_tts.list_voices.side_effect = RuntimeError("network error")

        result = list_voices()

        assert result == []


class TestGenerate:
    def test_generates_single_file(self, mock_edge_tts, tmp_path):
        target = tmp_path / "test.mp3"
        communicate_instance = mock_edge_tts.Communicate.return_value

        generate("sv-SE-SofieNeural", "hej", target)

        mock_edge_tts.Communicate.assert_called_once_with("hej", "sv-SE-SofieNeural")
        communicate_instance.save.assert_called_once_with(str(target))


class TestGenerateRange:
    def test_creates_all_number_files(self, mock_edge_tts, tmp_path):
        communicate_instance = mock_edge_tts.Communicate.return_value
        target_dir = tmp_path / "sv-SE-SofieNeural"

        generate_range(
            "sv-SE-SofieNeural",
            range(0, 3),
            [],
            target_dir,
        )

        assert target_dir.exists()
        assert communicate_instance.save.call_count == 3
        communicate_instance.save.assert_any_call(str(target_dir / "0.mp3"))
        communicate_instance.save.assert_any_call(str(target_dir / "1.mp3"))
        communicate_instance.save.assert_any_call(str(target_dir / "2.mp3"))

    def test_creates_phrase_files(self, mock_edge_tts, tmp_path):
        communicate_instance = mock_edge_tts.Communicate.return_value
        target_dir = tmp_path / "test-voice"
        texts = [
            VoiceFile("Testing", "Testing, one two three"),
            VoiceFile("Team", "Team"),
        ]

        generate_range(
            "test-voice",
            range(0, 1),
            texts,
            target_dir,
        )

        assert target_dir.exists()
        assert communicate_instance.save.call_count == 3
        communicate_instance.save.assert_any_call(str(target_dir / "0.mp3"))
        communicate_instance.save.assert_any_call(str(target_dir / "Testing.mp3"))
        communicate_instance.save.assert_any_call(str(target_dir / "Team.mp3"))

    def test_creates_target_directory(self, mock_edge_tts, tmp_path):
        target_dir = tmp_path / "new-voice" / "subdir"

        generate_range("test-voice", range(0, 1), [], target_dir)

        assert target_dir.exists()

    def test_calls_progress_callback(self, mock_edge_tts, tmp_path):
        target_dir = tmp_path / "progress-test"
        progress = MagicMock()

        generate_range(
            "test-voice",
            range(0, 3),
            [VoiceFile("Test", "test")],
            target_dir,
            progress_callback=progress,
        )

        assert progress.call_count == 4
        progress.assert_any_call(1, 4)
        progress.assert_any_call(2, 4)
        progress.assert_any_call(3, 4)
        progress.assert_any_call(4, 4)

    def test_progress_callback_none_does_not_raise(self, mock_edge_tts, tmp_path):
        target_dir = tmp_path / "no-progress"

        generate_range("test-voice", range(0, 2), [], target_dir)

        assert target_dir.exists()

    def test_total_includes_numbers_and_texts(self, mock_edge_tts, tmp_path):
        target_dir = tmp_path / "total-test"
        progress = MagicMock()

        generate_range(
            "test-voice",
            range(0, 10),
            [VoiceFile("A", "a"), VoiceFile("B", "b")],
            target_dir,
            progress_callback=progress,
        )

        assert progress.call_count == 12
        progress.assert_any_call(12, 12)
