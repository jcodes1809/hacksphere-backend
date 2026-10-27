"""Build backend.zip for Catalyst AppSail with all dependencies bundled.
Catalyst does NOT pip-install requirements for you, so packages are vendored into the zip.
Usage:  python make_zip.py            (x86_64 Linux wheels, Python 3.11)
        APPSAIL_ARCH=aarch64 python make_zip.py   (if the runtime turns out to be ARM)"""
import os
import pathlib
import shutil
import subprocess
import sys
import zipfile

ARCH = os.environ.get("APPSAIL_ARCH", "x86_64")
PYVER = os.environ.get("APPSAIL_PYTHON", "3.11")
BUILD = pathlib.Path("build_appsail")

shutil.rmtree(BUILD, ignore_errors=True)
BUILD.mkdir()

platforms = []
for p in (f"manylinux_2_28_{ARCH}", f"manylinux_2_27_{ARCH}", f"manylinux_2_24_{ARCH}",
          f"manylinux_2_17_{ARCH}", f"manylinux2014_{ARCH}"):
    platforms += ["--platform", p]

cmd = [sys.executable, "-m", "pip", "install", "--only-binary=:all:", *platforms,
       "--python-version", PYVER, "--implementation", "cp", "--target", str(BUILD),
       "-r", "requirements-deploy.txt"]
print("Installing Linux packages (this takes a minute)...")
subprocess.check_call(cmd)
# zcatalyst-sdk pins typing-extensions~=4.12, which clashes with pydantic; it is pure Python
# and its only other dependency (requests) is already installed, so add it without deps.
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--no-deps', '--only-binary=:all:',
                       '--target', str(BUILD), 'zcatalyst-sdk==1.4.0'])

sdk = [sys.executable, "-m", "pip", "install", "--only-binary=:all:", *platforms,
       "--python-version", PYVER, "--implementation", "cp", "--target", str(BUILD), "zcatalyst-sdk"]
if subprocess.call(sdk) != 0:
    print("Retrying SDK with --pre ...")
    subprocess.check_call(sdk + ["--pre"])

shutil.copytree("app", BUILD / "app", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
shutil.copy("requirements-deploy.txt", BUILD / "requirements.txt")

# shrink: remove bundled test suites and caches
for d in list(BUILD.rglob("tests")) + list(BUILD.rglob("__pycache__")):
    if d.is_dir():
        shutil.rmtree(d, ignore_errors=True)

for must in ("uvicorn", "fastapi", "pandas", "numpy", "zcatalyst_sdk", "app"):
    assert (BUILD / must).exists(), f"missing in build: {must}"

with zipfile.ZipFile("backend.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for f in BUILD.rglob("*"):
        if f.is_file():
            z.write(f, f.relative_to(BUILD))
print(f"backend.zip created ({os.path.getsize('backend.zip') / 1e6:.1f} MB), arch={ARCH}, python={PYVER}")
