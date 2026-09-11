from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import master


class WebsiteAiRenderCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_count = os.environ.pop("MASTERING_CANDIDATE_COUNT", None)
        self.previous_mode = os.environ.pop("MASTERING_SOURCE_MODE", None)

    def tearDown(self) -> None:
        os.environ.pop("MASTERING_CANDIDATE_COUNT", None)
        os.environ.pop("MASTERING_SOURCE_MODE", None)
        if self.previous_count is not None:
            os.environ["MASTERING_CANDIDATE_COUNT"] = self.previous_count
        if self.previous_mode is not None:
            os.environ["MASTERING_SOURCE_MODE"] = self.previous_mode

    def test_website_flags_are_removed_before_core_cli_parsing(self) -> None:
        args = master._prepare_ai_render_args([
            "--input",
            "song.wav",
            "--candidate-count=3",
            "--mode",
            "suno",
            "--style",
            "warm and punchy",
        ])

        self.assertEqual(args, ["--input", "song.wav", "--style", "warm and punchy"])
        self.assertEqual(os.environ["MASTERING_CANDIDATE_COUNT"], "3")
        self.assertEqual(os.environ["MASTERING_SOURCE_MODE"], "suno")

    def test_engineer_mode_rewrites_only_suno_specific_default_intent(self) -> None:
        args = master._prepare_ai_render_args([
            "--mode=engineer",
            "--style",
            "tame Suno AI high-end distortion, wider stereo image, analog warmth",
        ])

        self.assertEqual(
            args,
            [
                "--style",
                "transparent full-range tonal polish, wider stereo image, analog warmth",
            ],
        )
        self.assertEqual(os.environ["MASTERING_SOURCE_MODE"], "engineer")

    def test_invalid_candidate_count_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 5"):
            master._prepare_ai_render_args(["--candidate-count=6"])


class ChooseCompatibilityTests(unittest.TestCase):
    def test_choose_defaults_to_model_best_and_copies_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "original.wav"
            warm = root / "warm.wav"
            output = root / "selected.wav"
            report = root / "ai-mastering-report.json"

            original.write_bytes(b"original")
            warm.write_bytes(b"warm-master")
            report.write_text(
                json.dumps({
                    "input": str(original),
                    "best_candidate": "warm_analog",
                    "candidates": [
                        {"name": "original", "path": str(original), "score": 50.0},
                        {"name": "warm_analog", "path": str(warm), "score": 91.5},
                    ],
                }),
                encoding="utf-8",
            )

            selected = master._choose_from_report(
                report,
                output,
                interactive=True,
                input_fn=lambda _: "",
            )

            self.assertEqual(selected, "warm_analog")
            self.assertEqual(output.read_bytes(), b"warm-master")

    def test_choose_accepts_candidate_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.wav"
            second = root / "second.wav"
            output = root / "selected.wav"
            report = root / "ai-mastering-report.json"

            first.write_bytes(b"first")
            second.write_bytes(b"second")
            report.write_text(
                json.dumps({
                    "best_candidate": "first",
                    "candidates": [
                        {"name": "first", "path": str(first)},
                        {"name": "second", "path": str(second)},
                    ],
                }),
                encoding="utf-8",
            )

            selected = master._choose_from_report(
                report,
                output,
                interactive=True,
                input_fn=lambda _: "second",
            )

            self.assertEqual(selected, "second")
            self.assertEqual(output.read_bytes(), b"second")


if __name__ == "__main__":
    unittest.main()
