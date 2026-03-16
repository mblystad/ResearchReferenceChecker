from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BUILD_ROOT = ROOT / "build"
DIST_ROOT = ROOT / "dist"
PYI_WORK = BUILD_ROOT / "pyinstaller-work"
PYI_DIST = BUILD_ROOT / "pyinstaller-dist"
PYI_SPEC = BUILD_ROOT / "pyinstaller-spec"
APP_NAME = "ReferenceChecker"
RELEASE_NAME = "ReferenceChecker-windows-x64"
RELEASE_DIR = DIST_ROOT / RELEASE_NAME
ZIP_PATH = DIST_ROOT / f"{RELEASE_NAME}.zip"
RELEASE_README = ROOT / "RELEASE_README.txt"
QUICKSTART = ROOT / "USER_QUICKSTART.md"
PYINSTALLER_SEPARATOR = ";" if os.name == "nt" else ":"
CONDA_RUNTIME_DLLS = (
    "liblzma.dll",
    "LIBBZ2.dll",
    "libcrypto-3-x64.dll",
    "libssl-3-x64.dll",
    "ffi.dll",
    "libexpat.dll",
    "sqlite3.dll",
    "tcl86t.dll",
    "tk86t.dll",
)


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("zip.py currently builds the Windows release only.")

    _install_requirements(ROOT / "requirements.txt")
    _install_requirements(ROOT / "requirements-build.txt")
    pyinstaller_main = _load_pyinstaller()

    _remove_path(PYI_WORK)
    _remove_path(PYI_DIST)
    _remove_path(PYI_SPEC)
    _remove_path(RELEASE_DIR)
    _remove_path(ZIP_PATH)

    PYI_WORK.mkdir(parents=True, exist_ok=True)
    PYI_DIST.mkdir(parents=True, exist_ok=True)
    PYI_SPEC.mkdir(parents=True, exist_ok=True)
    DIST_ROOT.mkdir(parents=True, exist_ok=True)

    pyinstaller_main.run(_pyinstaller_args())

    built_dir = PYI_DIST / APP_NAME
    if not built_dir.exists():
        raise SystemExit(f"Build failed: {built_dir} was not created.")

    shutil.copytree(built_dir, RELEASE_DIR)
    _copy_release_docs(RELEASE_DIR)
    _copy_conda_runtime_dlls(RELEASE_DIR)
    _make_zip(RELEASE_DIR, ZIP_PATH)

    print("")
    print(f"Release folder: {RELEASE_DIR}")
    print(f"Release zip:    {ZIP_PATH}")


def _install_requirements(requirements_path: Path) -> None:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", str(requirements_path)],
        cwd=str(ROOT),
    )


def _load_pyinstaller():
    try:
        return importlib.import_module("PyInstaller.__main__")
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "PyInstaller is not available even after installing requirements-build.txt."
        ) from exc


def _pyinstaller_args() -> list[str]:
    return [
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        APP_NAME,
        "--distpath",
        str(PYI_DIST),
        "--workpath",
        str(PYI_WORK),
        "--specpath",
        str(PYI_SPEC),
        "--collect-all",
        "streamlit",
        "--add-data",
        _add_data("app.py", "."),
        "--add-data",
        _add_data("src", "src"),
        "--add-data",
        _add_data("reflogo.png", "."),
        "--add-data",
        _add_data(".streamlit", ".streamlit"),
        "--add-data",
        _add_data("data", "data"),
        "--add-data",
        _add_data("predatory_db_v7_with_norwegian_levels.csv", "data"),
        "--add-data",
        _add_data("pred_pub_list.csv", "data"),
        "--add-data",
        _add_data("pred_jour_list.csv", "data"),
        "run_app.py",
    ]


def _add_data(source: str, destination: str) -> str:
    return f"{ROOT / source}{PYINSTALLER_SEPARATOR}{destination}"


def _copy_release_docs(release_dir: Path) -> None:
    shutil.copy2(RELEASE_README, release_dir / "README.txt")
    shutil.copy2(QUICKSTART, release_dir / "USER_QUICKSTART.md")


def _copy_conda_runtime_dlls(release_dir: Path) -> None:
    # Conda-based Python environments keep important runtime DLLs in Library/bin.
    # Copy them into the release folder when present so the packaged app is portable.
    search_roots = [
        Path(sys.base_prefix) / "Library" / "bin",
        Path(sys.base_prefix) / "DLLs",
        Path(sys.prefix) / "Library" / "bin",
        Path(sys.prefix) / "DLLs",
    ]

    seen: set[Path] = set()
    for root in search_roots:
        if not root.exists():
            continue
        for dll_name in CONDA_RUNTIME_DLLS:
            candidate = root / dll_name
            target = release_dir / dll_name
            if candidate.exists() and candidate not in seen and not target.exists():
                shutil.copy2(candidate, target)
                seen.add(candidate)


def _make_zip(release_dir: Path, zip_path: Path) -> None:
    shutil.make_archive(
        base_name=str(zip_path.with_suffix("")),
        format="zip",
        root_dir=str(DIST_ROOT),
        base_dir=release_dir.name,
    )


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        path.unlink()


if __name__ == "__main__":
    main()
