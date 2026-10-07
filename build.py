import argparse
import io
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("variant", choices=["standalone", "combined"])
parser.add_argument("--wheel", type=Path)
options = parser.parse_args()
combined = options.variant == "combined"
app = ROOT / "build" / options.variant
app.mkdir(parents=True, exist_ok=True)
(app / "main.py").write_text(f"INTEGRATED = {combined}\n" + (ROOT / "demo.py").read_text(), encoding="utf-8")
dependencies = ['"flet==1.0.3"', '"flet-android-background"']
if options.wheel:
    dependencies[1] = f'"flet-android-background @ {options.wheel.resolve().as_uri()}"'
development = "" if options.wheel else f'''[tool.flet.dev_packages]
flet-android-background = "{(ROOT / "package").as_posix()}"
'''
if combined:
    dependencies.append('"flet-android-notifications==0.11.2"')
(app / "pyproject.toml").write_text(f'''
[project]
name = "background-{options.variant}"
version = "0.0.1"
requires-python = ">=3.11"
dependencies = [{", ".join(dependencies)}]
[tool.flet]
product = "Background {"Combined" if combined else "Only"}"
bundle_id = "dev.alexstoica.background.{options.variant}"
[tool.flet.app]
exclude = ["build", "generate.log"]
[tool.flet.flutter.pubspec.dependency_overrides]
jni = "1.1.0"
{development}
''', encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"
print(f"Building {options.variant}; log: {app / 'generate.log'}", flush=True)
with (app / "generate.log").open("w", encoding="utf-8") as log:
    result = subprocess.run(
        ["flet", "build", "apk", "--arch", "arm64-v8a", "--no-rich-output", "--yes",
         "--skip-flutter-doctor", "--no-compile-app", "--flutter-build-args=--debug", "-v"],
        cwd=app, stdout=log, stderr=subprocess.STDOUT,
    )
if result.returncode:
    output = re.sub(r"\s+", " ", (app / "generate.log").read_text(encoding="utf-8"))
    failures = re.findall(r"Execution failed for task '([^']+)'", output)
    if not combined or failures != [":app:checkDebugAarMetadata"] or "requires core library desugaring" not in output:
        raise SystemExit(f"Build failed; see {app / 'generate.log'}")
if combined:
    from flet_android_notifications.patcher import patch_android_project
    patch_android_project(app / "build/flutter")
from flet_android_background.android import configure_android_project
configure_android_project(app / "build/flutter", service_type="dataSync")
flutter = os.environ.get("FLUTTER_BIN") or shutil.which("flutter")
if not flutter:
    raise SystemExit("Set FLUTTER_BIN or add Flutter to PATH.")
env = dict(os.environ, SERIOUS_PYTHON_APP=str(app / "build/python-app"),
           SERIOUS_PYTHON_SITE_PACKAGES=str(app / "build/site-packages"),
           SERIOUS_PYTHON_VERSION=(app / "build/.python-version").read_text().strip())
subprocess.run([flutter, "build", "apk", "--debug", "--build-name", "0.0.1",
                "--target-platform", "android-arm64"],
               cwd=app / "build/flutter", env=env, check=True)
apk = ROOT / "build" / f"{options.variant}.apk"
shutil.copy2(app / "build/flutter/build/app/outputs/flutter-apk/app-debug.apk", apk)
with zipfile.ZipFile(apk) as archive:
    for name in ("app", "stdlib", "sitepackages"):
        with zipfile.ZipFile(io.BytesIO(archive.read(f"assets/{name}.zip"))) as contents:
            if contents.testzip() is not None:
                raise RuntimeError(f"Corrupt {name} archive")
print(apk)
