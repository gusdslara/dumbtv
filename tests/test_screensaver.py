"""scripts/screensaver.sh against a pretend Fire TV: the images reach the launcher's media
folder, the TV's screensaver points at dumbtv home's, and --off hands the TV's own one back.

Run: python3 -m unittest discover -s tests -v
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FOLDER = "/sdcard/Android/media/tv.dumbtv.home/screensaver"
OURS = "tv.dumbtv.home/.Screensaver"
AMAZON = "com.amazon.ftv.screensaver/.app.services.ScreensaverService"


class ScreensaverTest(unittest.TestCase):
    def run_script(self, *args, service=True, current=AMAZON,
                   names=("Marvel - Loki - 1.jpg", "Anime - Frieren - 2.png", "notes.txt")):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        tmp = Path(holder.name)
        images = tmp / "images"
        images.mkdir()
        for name in names:
            (images / name).write_bytes(b"image")
        pushed = tmp / "pushed"
        state = tmp / "state.json"
        state.write_text(json.dumps({
            "packages": {"tv.dumbtv.home": {"system": False, "enabled": True}},
            "components": {"tv.dumbtv.home": [OURS] if service else []},
            "settings": {"secure/screensaver_components": current,
                         "secure/screensaver_default_component": AMAZON},
            "sdk": 28, "pushed": str(pushed)}))
        log = tmp / "commands.log"
        log.touch()
        env = dict(os.environ, ADB=str(ROOT / "tests" / "fake_tv.py"), ADB_SERIAL="test-tv",
                   FAKE_TV_STATE=str(state), FAKE_TV_LOG=str(log))
        result = subprocess.run(["bash", str(ROOT / "scripts" / "screensaver.sh"), "-y", *args, str(images)],
                                env=env, capture_output=True, text=True, timeout=60)
        files = sorted(p.name for p in pushed.iterdir()) if pushed.exists() else []
        settings = json.loads(state.read_text()).get("settings", {})
        return result, log.read_text().splitlines(), files, settings

    def test_images_reach_the_media_folder_and_the_screensaver_is_ours(self):
        result, commands, files, settings = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(files, ["Anime - Frieren - 2.png", "Marvel - Loki - 1.jpg"])
        self.assertIn(f"mkdir -p '{FOLDER}'", commands)
        self.assertEqual(settings["secure/screensaver_components"], OURS)
        self.assertNotIn("system/screen_off_timeout", settings)

    def test_minutes_sets_the_idle_timeout(self):
        result, _, _, settings = self.run_script("--minutes", "5")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(settings["system/screen_off_timeout"], "300000")

    def test_a_launcher_without_the_screensaver_changes_nothing(self):
        result, _, files, settings = self.run_script(service=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no screensaver", result.stderr)
        self.assertEqual(files, [])
        self.assertEqual(settings["secure/screensaver_components"], AMAZON)

    def test_dry_run_changes_nothing(self):
        result, _, files, settings = self.run_script("--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(files, [])
        self.assertEqual(settings["secure/screensaver_components"], AMAZON)

    def test_off_gives_the_tvs_own_back(self):
        result, _, files, settings = self.run_script("--off", current=OURS)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(files, [])
        self.assertEqual(settings["secure/screensaver_components"], AMAZON)

    def test_off_leaves_another_screensaver_alone(self):
        result, _, _, settings = self.run_script("--off", current="com.android.dreams.basic/.Colors")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(settings["secure/screensaver_components"], "com.android.dreams.basic/.Colors")


if __name__ == "__main__":
    unittest.main()
