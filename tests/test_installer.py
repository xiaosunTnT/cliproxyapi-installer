"""Offline regression tests: python3 -m unittest discover -s tests -v."""

import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest


INSTALLER = Path(__file__).resolve().parents[1] / "cliproxyapi-installer"


def release(*platforms):
    return json.dumps({
        "tag_name": "v8.0.27",
        "assets": [
            {"browser_download_url":
             f"https://example.test/CLIProxyAPI_8.0.27_{platform}.tar.gz"}
            for platform in platforms
        ],
    })


class InstallerTests(unittest.TestCase):
    def run_bash(self, commands, **variables):
        environment = dict(os.environ, CPA_INSTALLER=str(INSTALLER), **variables)
        return subprocess.run(
            ["bash", "-c", '''source "$CPA_INSTALLER"
if [[ -n "${CPA_TEST_ROOT:-}" ]]; then
    SYSTEM_SERVICE_FILE="$CPA_TEST_ROOT/system.service"
    USER_SERVICE_FILE="$CPA_TEST_ROOT/user.service"
fi
''' + commands],
            env=environment, capture_output=True, text=True, timeout=10,
        )

    def test_direct_and_piped_invocation(self):
        for command, content in (
            (["bash", str(INSTALLER), "--help"], None),
            (["bash", "-s", "--", "--help"], INSTALLER.read_text()),
        ):
            with self.subTest(command=command):
                result = subprocess.run(
                    command, input=content, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Usage: cliproxyapi-installer", result.stdout)

    def test_architecture_aliases(self):
        for machine, platform in (
            ("aarch64", "linux_arm64"), ("arm64", "linux_arm64"),
            ("x86_64", "linux_amd64"), ("amd64", "linux_amd64"),
        ):
            with self.subTest(machine=machine):
                result = self.run_bash(
                    'uname() { printf "%s\\n" "$CPA_MACHINE"; }; detect_linux_arch',
                    CPA_MACHINE=machine,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), platform)

    def test_unsupported_architecture_is_visible(self):
        result = self.run_bash(
            'uname() { echo armv7l; }; platform=$(detect_linux_arch)'
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unsupported architecture: armv7l", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_release_asset_names(self):
        for requested, assets, selected in (
            ("linux_arm64", ("linux_aarch64",), "linux_aarch64"),
            ("linux_arm64", ("linux_arm64",), "linux_arm64"),
            ("linux_aarch64", ("linux_arm64",), "linux_arm64"),
            ("linux_arm64", ("linux_arm64", "linux_aarch64"), "linux_aarch64"),
            ("linux_amd64", ("linux_aarch64", "linux_amd64"), "linux_amd64"),
        ):
            with self.subTest(requested=requested, assets=assets):
                result = self.run_bash(
                    'data=$(extract_release_info "$CPA_RELEASE" "$CPA_PLATFORM"); '
                    'printf "%s\\n" "$data"',
                    CPA_RELEASE=release(*assets), CPA_PLATFORM=requested,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    result.stdout.strip(),
                    f"8.0.27|https://example.test/CLIProxyAPI_8.0.27_{selected}.tar.gz",
                )

    def test_missing_asset_explains_failure(self):
        result = self.run_bash(
            'data=$(extract_release_info "$CPA_RELEASE" linux_arm64)',
            CPA_RELEASE=release("linux_amd64", "linux_aarch64_no-plugin"),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("No compatible release archive found for linux_arm64", result.stderr)
        self.assertIn("CLIProxyAPI_8.0.27_linux_amd64.tar.gz", result.stderr)

    def test_similar_filename_is_not_selected(self):
        data = release("linux_aarch64").replace("8.0.27_linux", "8x0x27_linux")
        result = self.run_bash(
            'data=$(extract_release_info "$CPA_RELEASE" linux_arm64)',
            CPA_RELEASE=data,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No compatible release archive", result.stderr)

    def test_invalid_release_explains_failure(self):
        for data in ('{"message":"API rate limit exceeded"}', "<html>Error</html>", ""):
            with self.subTest(data=data):
                result = self.run_bash(
                    'data=$(extract_release_info "$CPA_RELEASE" linux_arm64)',
                    CPA_RELEASE=data,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Failed to extract version", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_fetch_returns_only_json_on_stdout(self):
        result = self.run_bash(
            'curl() { printf "%s\\n" "$CPA_RELEASE"; }; '
            'data=$(fetch_release_info); printf "%s\\n" "$data"',
            CPA_RELEASE=release("linux_aarch64"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), json.loads(release("linux_aarch64")))
        self.assertIn("Fetching latest release information", result.stderr)

    def test_fetch_failure_and_empty_response_are_visible(self):
        for body in ("return 22", "return 0"):
            with self.subTest(body=body):
                result = self.run_bash(
                    f"curl() {{ {body}; }}; data=$(fetch_release_info)"
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Failed to fetch release information", result.stderr)

    def test_wget_fallback(self):
        result = self.run_bash(
            'command() { if [[ "$*" == "-v curl" ]]; then return 1; fi; '
            'builtin command "$@"; }; '
            'wget() { printf "%s\\n" "$CPA_RELEASE"; }; '
            'data=$(fetch_release_info); printf "%s\\n" "$data"',
            CPA_RELEASE=release("linux_aarch64"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), json.loads(release("linux_aarch64")))

    def test_wget_failure_is_visible(self):
        result = self.run_bash(
            'command() { if [[ "$*" == "-v curl" ]]; then return 1; fi; '
            'builtin command "$@"; }; '
            'wget() { return 8; }; data=$(fetch_release_info)'
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Failed to fetch release information", result.stderr)

    def test_download_failure_does_not_accept_existing_empty_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "download"
            output.touch()
            result = self.run_bash(
                'curl() { return 22; }; download_file https://example.test/archive "$CPA_OUTPUT"',
                CPA_OUTPUT=str(output),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Failed to download", result.stderr)
            self.assertNotIn("Download completed", result.stderr)

    def test_empty_download_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_bash(
                'curl() { return 0; }; download_file https://example.test/archive "$CPA_OUTPUT"',
                CPA_OUTPUT=str(Path(directory) / "download"),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Downloaded file is empty", result.stderr)

    def test_cleanup_removes_only_installer_download(self):
        with tempfile.TemporaryDirectory() as directory:
            owned = Path(directory) / "download"
            unrelated = Path(directory) / "tmp.unrelated"
            owned.touch()
            unrelated.touch()
            result = self.run_bash(
                'DOWNLOAD_TEMP_FILE="$CPA_OUTPUT"; cleanup', CPA_OUTPUT=str(owned),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(owned.exists())
            self.assertTrue(unrelated.exists())

    def test_backup_path_is_not_contaminated_by_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.yaml"
            config.write_text("custom: preserved\n")
            result = self.run_bash(
                'INSTALL_DIR="$CPA_TEST_ROOT"; backup=$(backup_config); '
                'test -f "$backup"; printf "%s\\n" "$backup"',
                CPA_TEST_ROOT=directory,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(Path(result.stdout.strip()).read_text(), config.read_text())
            self.assertIn("Configuration backed up", result.stderr)

    def test_failed_install_download_cleans_up_without_marking_installed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_bash('''
INSTALL_DIR="$CPA_TEST_ROOT/install"
check_service_permissions() { :; }
uname() { echo aarch64; }
curl() {
    if [[ "$*" == *" -o "* ]]; then return 22; fi
    printf '%s\\n' "$CPA_RELEASE"
}
mktemp() { command mktemp "$CPA_TEST_ROOT/download.XXXXXX"; }
trap cleanup EXIT
main install
''', CPA_TEST_ROOT=directory, CPA_RELEASE=release("linux_aarch64"))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Failed to download", result.stderr)
            root = Path(directory)
            self.assertFalse((root / "install" / "version.txt").exists())
            self.assertEqual(list(root.glob("download.*")), [])

    def test_installation_continues_after_arm_detection(self):
        # Use the real extraction/configuration/version code. Only replace network,
        # systemd, and GNU-specific version cleanup on the macOS test host.
        for platform in ("linux_aarch64", "linux_arm64", "linux_amd64"):
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                install = root / "install"
                install.mkdir()
                config = install / "config.yaml"
                config.write_text('api-keys:\n  - "preserved-user-key"\n')
                archive = root / "fixture.tar.gz"
                with tarfile.open(archive, "w:gz") as bundle:
                    content = b"#!/bin/sh\necho fixture-binary\n"
                    info = tarfile.TarInfo("cli-proxy-api")
                    info.size = len(content)
                    bundle.addfile(info, io.BytesIO(content))
                result = self.run_bash('''
INSTALL_DIR="$CPA_TEST_ROOT/install"
check_service_permissions() { :; }
uname() { echo "$CPA_MACHINE"; }
curl() {
    local output=""
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "-o" ]]; then output="$2"; shift; fi
        shift
    done
    if [[ -n "$output" ]]; then
        cp "$CPA_TEST_ROOT/fixture.tar.gz" "$output"
    else
        printf '%s\\n' "$CPA_RELEASE"
    fi
}
mktemp() { command mktemp "$CPA_TEST_ROOT/download.XXXXXX"; }
create_systemd_service() { :; }
cleanup_old_versions() { :; }
show_authentication_info() { :; }
show_quick_start() { :; }
trap cleanup EXIT
main install
''', CPA_TEST_ROOT=directory, CPA_RELEASE=release(platform),
                    CPA_MACHINE="x86_64" if platform == "linux_amd64" else "aarch64")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("installed successfully", result.stderr)
                self.assertEqual((install / "version.txt").read_text().strip(), "8.0.27")
                self.assertTrue(os.access(install / "cli-proxy-api", os.X_OK))
                self.assertIn("preserved-user-key", config.read_text())
                self.assertEqual(list(root.glob("download.*")), [])

    def test_main_reports_release_failure_before_writing_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_bash('''
INSTALL_DIR="$CPA_TEST_ROOT/install"
check_service_permissions() { :; }
uname() { echo aarch64; }
curl() { printf '%s\\n' "$CPA_RELEASE"; }
main install
''', CPA_TEST_ROOT=directory, CPA_RELEASE=release("linux_amd64"))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Detected platform: linux_arm64", result.stderr)
            self.assertIn("No compatible release archive", result.stderr)
            self.assertFalse((Path(directory) / "install").exists())


class SystemServiceTests(unittest.TestCase):
    run_bash = InstallerTests.run_bash

    SERVICE_MOCKS = '''
INSTALL_DIR="$CPA_TEST_ROOT/install"
check_service_permissions() { :; }
run_as_root() { "$@"; }
sleep() { :; }
systemctl() {
    printf '%s\\n' "$*" >> "$CPA_TEST_ROOT/events"
    case "$*" in
        "--user is-active "*) return "${CPA_LEGACY_RUNNING:-1}" ;;
        "--user is-enabled "*) return "${CPA_LEGACY_ENABLED:-1}" ;;
        "--user disable --now "*) return "${CPA_DISABLE_ERROR:-0}" ;;
        "is-active "*) return "${CPA_SYSTEM_RUNNING:-1}" ;;
        "restart "*|"start "*) CPA_SYSTEM_RUNNING=0 ;;
    esac
}
'''

    def make_install(self, root, legacy=False):
        install = root / "install"
        install.mkdir()
        binary = install / "cli-proxy-api"
        binary.write_text("#!/bin/sh\necho preserved-binary\n")
        binary.chmod(0o755)
        (install / "config.yaml").write_text("custom: preserved\n")
        (install / "version.txt").write_text("8.0.27\n")
        if legacy:
            (root / "user.service").write_text("[Install]\nWantedBy=default.target\n")
        return install

    def test_system_unit_keeps_original_user_and_home(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install = self.make_install(root)
            result = self.run_bash(
                self.SERVICE_MOCKS + 'create_systemd_service "$INSTALL_DIR"',
                CPA_TEST_ROOT=directory,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            unit = (root / "system.service").read_text()
            self.assertIn(f"User={subprocess.check_output(['id', '-un'], text=True).strip()}", unit)
            self.assertIn(f"Group={subprocess.check_output(['id', '-gn'], text=True).strip()}", unit)
            self.assertIn(f'Environment="HOME={os.environ["HOME"]}"', unit)
            self.assertIn(f"WorkingDirectory={install}", unit)
            self.assertIn(f"ExecStart={install}/cli-proxy-api", unit)
            self.assertIn("WantedBy=multi-user.target", unit)
            self.assertNotIn("WantedBy=default.target", unit)
            self.assertEqual((root / "events").read_text(), "daemon-reload\n")

    def test_migration_preserves_running_and_enabled_states(self):
        for running in (False, True):
            for enabled in (False, True):
                with self.subTest(running=running, enabled=enabled), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    install = self.make_install(root, legacy=True)
                    result = self.run_bash(
                        self.SERVICE_MOCKS + "main setup-service",
                        CPA_TEST_ROOT=directory,
                        CPA_LEGACY_RUNNING="0" if running else "1",
                        CPA_LEGACY_ENABLED="0" if enabled else "1",
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertFalse((root / "user.service").exists())
                    self.assertTrue((root / "system.service").exists())
                    events = (root / "events").read_text().splitlines()
                    self.assertIn("--user disable --now cliproxyapi.service", events)
                    self.assertEqual("enable cliproxyapi.service" in events, enabled)
                    self.assertEqual("restart cliproxyapi.service" in events, running)
                    if running:
                        self.assertLess(
                            events.index("--user disable --now cliproxyapi.service"),
                            events.index("restart cliproxyapi.service"),
                        )
                    self.assertEqual((install / "config.yaml").read_text(), "custom: preserved\n")
                    self.assertIn("preserved-binary", (install / "cli-proxy-api").read_text())

    def test_failed_legacy_stop_never_starts_second_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_install(root, legacy=True)
            result = self.run_bash(
                self.SERVICE_MOCKS + "main setup-service",
                CPA_TEST_ROOT=directory, CPA_LEGACY_RUNNING="0",
                CPA_LEGACY_ENABLED="0", CPA_DISABLE_ERROR="1",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Could not stop the legacy user service", result.stderr)
            self.assertTrue((root / "user.service").exists())
            events = (root / "events").read_text().splitlines()
            self.assertNotIn("restart cliproxyapi.service", events)
            self.assertNotIn("enable cliproxyapi.service", events)

    def test_already_current_version_still_migrates_service(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_install(root, legacy=True)
            result = self.run_bash(self.SERVICE_MOCKS + '''
uname() { echo aarch64; }
curl() { printf '%s\\n' "$CPA_RELEASE"; }
main upgrade
''', CPA_TEST_ROOT=directory, CPA_RELEASE=release("linux_aarch64"),
                CPA_LEGACY_RUNNING="0", CPA_LEGACY_ENABLED="0")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("already up to date", result.stderr)
            self.assertFalse((root / "user.service").exists())
            self.assertTrue((root / "system.service").exists())
            self.assertIn("restart cliproxyapi.service", (root / "events").read_text())

    def test_service_repair_does_not_start_stopped_service(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_install(root)
            result = self.run_bash(
                self.SERVICE_MOCKS + "main setup-service", CPA_TEST_ROOT=directory,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("restart cliproxyapi.service", (root / "events").read_text())

    def test_upgrade_migrates_running_legacy_service_after_download(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install = self.make_install(root, legacy=True)
            (install / "version.txt").write_text("8.0.26\n")
            with tarfile.open(root / "fixture.tar.gz", "w:gz") as bundle:
                content = b"#!/bin/sh\necho upgraded-binary\n"
                info = tarfile.TarInfo("cli-proxy-api")
                info.size = len(content)
                bundle.addfile(info, io.BytesIO(content))
            result = self.run_bash(self.SERVICE_MOCKS + '''
uname() { echo aarch64; }
curl() { printf '%s\\n' "$CPA_RELEASE"; }
download_file() {
    if grep -q -- 'disable --now' "$CPA_TEST_ROOT/events"; then return 1; fi
    cp "$CPA_TEST_ROOT/fixture.tar.gz" "$2"
}
mktemp() { command mktemp "$CPA_TEST_ROOT/download.XXXXXX"; }
is_cliproxyapi_running() { return 1; }
cleanup_old_versions() { :; }
trap cleanup EXIT
main upgrade
''', CPA_TEST_ROOT=directory, CPA_RELEASE=release("linux_aarch64"),
                CPA_LEGACY_RUNNING="0", CPA_LEGACY_ENABLED="0")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / "user.service").exists())
            self.assertTrue((root / "system.service").exists())
            self.assertIn("upgraded-binary", (install / "cli-proxy-api").read_text())
            self.assertEqual((install / "version.txt").read_text(), "8.0.27\n")
            self.assertEqual((install / "config.yaml").read_text(), "custom: preserved\n")
            backups = list((install / "config_backup").glob("*.yaml"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), "custom: preserved\n")
            events = (root / "events").read_text().splitlines()
            self.assertIn("enable cliproxyapi.service", events)
            self.assertLess(
                events.index("--user disable --now cliproxyapi.service"),
                events.index("restart cliproxyapi.service"),
            )

    def test_uninstall_removes_and_stops_system_service(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install = self.make_install(root)
            (root / "system.service").touch()
            result = self.run_bash(
                self.SERVICE_MOCKS + "main uninstall <<< y", CPA_TEST_ROOT=directory,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(install.exists())
            self.assertFalse((root / "system.service").exists())
            self.assertIn("disable --now cliproxyapi.service", (root / "events").read_text())
            self.assertIn("daemon-reload", (root / "events").read_text())

    def test_permission_checks_fail_before_service_changes(self):
        result = self.run_bash('''
command() {
    if [[ "$*" == "-v systemctl" ]]; then return 1; fi
    builtin command "$@"
}
check_service_permissions
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires Linux with systemd", result.stderr)

    def test_setup_service_requires_existing_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_bash(
                self.SERVICE_MOCKS + "main setup-service", CPA_TEST_ROOT=directory,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Install it first", result.stderr)
            self.assertFalse((Path(directory) / "system.service").exists())


if __name__ == "__main__":
    unittest.main()
