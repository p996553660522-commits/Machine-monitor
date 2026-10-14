"""Test exact Git snapshots, build deterministic installers and publish releases.

Local build needs Python, Node and Git. --publish additionally uses GH_TOKEN;
GitHub Actions supplies its short-lived repository token. Never moves old tags.
"""
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = "p996553660522-commits/Machine-monitor"
COMPONENT = "custom_components/machine_monitor/"
PREFIXES = ("custom_components/", "docs/", "firmware/", "scripts/", "tests/", "release_notes/", ".github/")
ROOT_FILES = {"README.md", "AGENTS.md", "CHANGELOG.md", ".gitignore", "releases.json"}


def validate_catalog(data):
    if data.get("schema") != 1 or not isinstance(data.get("releases"), list):
        raise ValueError("Unsupported release catalog")
    tags = set()
    for item in data["releases"]:
        version = item["version"]
        kind = item["kind"]
        tag = ("v" if kind == "integration" else "firmware-v") + version
        if kind not in ("integration", "firmware") or not re.fullmatch(r"\d+\.\d+\.\d+", version):
            raise ValueError("Invalid release kind/version")
        if item["tag"] != tag or tag in tags or not re.fullmatch(r"[0-9a-f]{40}", item["commit"]):
            raise ValueError("Duplicate tag or unpinned commit")
        if item["notes"] != f"release_notes/{tag}.md":
            raise ValueError("Invalid notes path")
        if not isinstance(item["latest"], bool) or not isinstance(item["prerelease"], bool):
            raise ValueError("Invalid release flags")
        if item["latest"] and (kind != "integration" or item["prerelease"]):
            raise ValueError("Latest must be a stable integration")
        tags.add(tag)
    if sum(item["latest"] for item in data["releases"]) != 1:
        raise ValueError("Choose exactly one latest stable integration")
    return data["releases"]


def snapshot(commit):
    payload = subprocess.check_output(["git", "archive", "--format=zip", commit], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        files = {info.filename: archive.read(info) for info in archive.infolist() if not info.is_dir()}
    for name in files:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError("Unsafe archive path")
    return files


def public_file(name):
    path = PurePosixPath(name)
    return (name in ROOT_FILES or name.startswith(PREFIXES)) and not any(
        part in (".storage", "__pycache__", ".git", "node_modules", ".venv")
        or part.startswith(".env") for part in path.parts
    ) and not name.endswith((".pyc", ".log", ".elf", ".bin", ".map")) and path.name not in (
        "secrets.yaml", "configuration.yaml")


def zip_bytes(files):
    """Stable ordering/timestamps allow independent checksum verification."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, payload in sorted(files.items()):
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                raise ValueError("Unsafe package path")
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload)
    return out.getvalue()


def installation(item):
    return f"""# Установка {item['tag']}

Точный исходный коммит: {item['commit']}. Прошивка снимка: {item['firmware']}.
Схема истории интеграции: {item['history_schema']}.

1. Скачайте ZIP из Assets выбранного GitHub Release и SHA256SUMS.txt.
2. Проверьте SHA256 (PowerShell: Get-FileHash -Algorithm SHA256 <архив>).
3. Сохраните полный HA backup с конфигурацией и .storage до обновления.
4. Из integration ZIP скопируйте только custom_components/machine_monitor в
   /config/custom_components/machine_monitor. Не создавайте двойную вложенность.
   При замене на старую версию уберите оставшиеся файлы более новой версии;
   используйте целую папку из выбранного пакета. Сначала сохраните старую папку.
5. Перезапустите HA и обновите браузер. Откройте боковое меню Machine Monitor.

Firmware ZIP содержит Arduino source, а не универсальный готовый бинарник.
Откройте firmware/MachineMonitor/MachineMonitor.ino, выберите свою плату ESP32
и PubSubClient, соберите скетч. При обновлении интеграции перепрошивка необязательна.
Подробности и ограничения этой версии: RELEASE_NOTES.md.

## Откат

Старый код не обязан понимать новые профили и схему истории. При откате 1.4.0
(schema 4) на 1.2.2/1.3.0 (schema 3) восстановите согласованную резервную копию
настроек HA, Machine Monitor profiles/history и папки интеграции ДО обновления.
Не понижайте номер схемы вручную и не удаляйте историю для обхода ошибки.
Записи после даты резервной копии в старую версию автоматически не переносятся;
сохраните также backup нового состояния, если хотите вернуться к нему позже.
Не меняйте ESP32 прошивку одновременно с откатом интеграции без необходимости.

Архивы не содержат пользовательских профилей, истории, MQTT/Wi-Fi паролей.
Автотесты используют HA stubs и минимальный DOM; совместимость со всеми версиями
HA и электрическая проверка устройства не заявляются.
""".encode("utf-8")


def validate_snapshot(item, files):
    firmware = files["firmware/MachineMonitor/MachineMonitor.ino"].decode("utf-8-sig")
    if f'\\"sw_version\\":\\"{item["firmware"]}\\"' not in firmware:
        raise ValueError(f"Firmware version mismatch: {item['tag']}")
    if item["kind"] == "integration":
        manifest = json.loads(files[COMPONENT + "manifest.json"])
        if manifest["version"] != item["version"]:
            raise ValueError("Manifest version does not match release")
        storage = files[COMPONENT + "storage.py"].decode("utf-8-sig")
        if not re.search(r'"history_schema_version"\s*:\s*' + str(item["history_schema"]) + r'\b', storage):
            raise ValueError("History schema does not match release")
    for name, payload in files.items():
        if name.endswith(".py"):
            ast.parse(payload.decode("utf-8-sig"), filename=name)
        if name.endswith(".json"):
            json.loads(payload)
        if re.search(rb"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----", payload):
            raise ValueError("Secret pattern in published source: " + name)


def test_snapshot(item, files):
    with tempfile.TemporaryDirectory(prefix="machine-monitor-release-") as tmp:
        directory = Path(tmp)
        for name, payload in files.items():
            destination = directory / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        commands = []
        if item["kind"] == "integration":
            commands += [[os.sys.executable, "-B", "-m", "unittest", "discover", "-s", COMPONENT + "tests", "-q"],
                         ["node", "--check", COMPONENT + "frontend/machine_monitor_card.js"],
                         ["node", "--test", *sorted(str(p.relative_to(directory)) for p in (directory / COMPONENT / "tests").glob("*.test.cjs"))]]
        if (directory / "firmware/tests").is_dir():
            commands.append([os.sys.executable, "-B", "-m", "unittest", "discover", "-s", "firmware/tests", "-q"])
        for command in commands:
            subprocess.run(command, cwd=directory, check=True)


def build(item, files, out, notes):
    validate_snapshot(item, files)
    release_dir = out / item["tag"]
    release_dir.mkdir(parents=True, exist_ok=True)
    metadata = json.dumps(item, ensure_ascii=False, indent=2).encode("utf-8")
    extras = {"INSTALL_RU.md": installation(item), "RELEASE_NOTES.md": notes, "release.json": metadata}
    packages = {}
    if item["kind"] == "integration":
        integration = {n: p for n, p in files.items() if n.startswith(COMPONENT) and "tests" not in PurePosixPath(n).parts and public_file(n)}
        packages[f"machine-monitor-{item['version']}.zip"] = {**integration, **extras}
    firmware = {n: p for n, p in files.items() if (n.startswith("firmware/MachineMonitor/") or n == "docs/FIRMWARE_RU.md") and public_file(n)}
    packages[f"machine-monitor-firmware-{item['firmware']}.zip"] = {**firmware, **extras}
    packages[f"machine-monitor-source-{item['tag']}.zip"] = {
        **{f"Machine-monitor-{item['tag']}/{n}": p for n, p in files.items() if public_file(n)},
        **{f"Machine-monitor-{item['tag']}/{n}": p for n, p in extras.items()}}
    checksums = []
    for name, contents in packages.items():
        payload = zip_bytes(contents)
        (release_dir / name).write_bytes(payload)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if archive.testzip() is not None:
                raise ValueError("Invalid ZIP")
            if {i.filename: archive.read(i) for i in archive.infolist()} != contents:
                raise ValueError("Package round-trip mismatch")
        checksums.append(hashlib.sha256(payload).hexdigest() + "  " + name)
    (release_dir / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    (release_dir / "release.json").write_bytes(metadata)
    (release_dir / "INSTALL_RU.md").write_bytes(installation(item))
    (release_dir / "RELEASE_NOTES.md").write_bytes(notes)
    return release_dir


def api(path, token, data=None, method="GET", raw=False):
    url = "https://api.github.com/repos/" + REPO + "/" + path
    payload = None if data is None else json.dumps(data).encode()
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "User-Agent": "Machine-Monitor-release"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    try:
        with urlopen(Request(url, payload, headers, method=method), timeout=60) as response:
            body = response.read()
            return body if raw else json.loads(body)
    except HTTPError as error:
        if error.code == 404 and method == "GET":
            return None
        raise RuntimeError(f"GitHub {method} {path}: HTTP {error.code}") from None


def publish(item, directory, token):
    tag = item["tag"]
    reference = api("git/ref/tags/" + tag, token)
    if reference:
        obj = reference["object"]
        while obj["type"] == "tag":
            obj = api("git/tags/" + obj["sha"], token)["object"]
        if obj["type"] != "commit" or obj["sha"] != item["commit"]:
            raise ValueError("Refusing to move existing version tag: " + tag)
    else:
        api("git/refs", token, {"ref": "refs/tags/" + tag, "sha": item["commit"]}, "POST")
    release = api("releases/tags/" + tag, token)
    if release is None:
        release = api("releases", token, {"tag_name": tag, "target_commitish": item["commit"],
            "name": "Machine Monitor " + tag, "body": (directory / "RELEASE_NOTES.md").read_text(encoding="utf-8"),
            "draft": True, "prerelease": item["prerelease"], "make_latest": "false"}, "POST")
    assets = {asset["name"]: asset for asset in api(f"releases/{release['id']}/assets?per_page=100", token)}
    for path in sorted(directory.iterdir()):
        payload = path.read_bytes()
        expected = "sha256:" + hashlib.sha256(payload).hexdigest()
        if path.name in assets:
            asset = assets[path.name]
            digest = asset.get("digest")
            if digest is None:
                with urlopen(asset["browser_download_url"], timeout=60) as response:
                    digest = "sha256:" + hashlib.sha256(response.read()).hexdigest()
            if digest != expected:
                raise ValueError("Refusing to replace existing release asset: " + path.name)
            continue
        if not release["draft"]:
            raise ValueError("Published release is incomplete; refusing silent changes: " + tag)
        url = f"https://uploads.github.com/repos/{REPO}/releases/{release['id']}/assets?name=" + quote(path.name)
        headers = {"Authorization": "Bearer " + token, "Content-Type": "application/octet-stream", "User-Agent": "Machine-Monitor-release"}
        with urlopen(Request(url, payload, headers, method="POST"), timeout=60) as response:
            uploaded = json.loads(response.read())
            if uploaded.get("digest") and uploaded["digest"] != expected:
                raise ValueError("Upload checksum mismatch")
    if release["draft"]:
        api(f"releases/{release['id']}", token, {"draft": False, "make_latest": "true" if item["latest"] else "false"}, "PATCH")
    print("Published / verified:", tag, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    entries = validate_catalog(json.loads((ROOT / "releases.json").read_text(encoding="utf-8")))
    current = json.loads((ROOT / COMPONENT / "manifest.json").read_text(encoding="utf-8"))["version"]
    if next(item["version"] for item in entries if item["latest"]) != current:
        raise ValueError("New integration version needs a pinned catalog entry and release notes")
    token = os.environ.get("GH_TOKEN") if args.publish else None
    if args.publish and not token:
        raise ValueError("--publish needs GH_TOKEN (provided by GitHub Actions)")
    tested, built = set(), []
    for item in entries:
        print("Validating:", item["tag"], item["commit"], flush=True)
        files = snapshot(item["commit"])
        key = (item["commit"], item["kind"])
        if key not in tested:
            test_snapshot(item, files)
            tested.add(key)
        built.append((item, build(item, files, args.out, (ROOT / item["notes"]).read_text(encoding="utf-8").encode("utf-8"))))
    # No public release mutation until every selected snapshot/package passed.
    if args.publish:
        for item, directory in built:
            publish(item, directory, token)


if __name__ == "__main__":
    main()
