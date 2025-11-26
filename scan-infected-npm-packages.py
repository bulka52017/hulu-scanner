
import os
import csv
import json
import subprocess
from pathlib import Path
from typing import Optional

# === CONFIG ===
CSV_FILE = "shai-hulud-2-packages.csv"
HOME_DIR = str(Path.home())
ADDITIONAL_SEARCH_DIRS = [
    "/usr/local/lib/node_modules",      # Homebrew Intel
    "/opt/homebrew/lib/node_modules",   # Homebrew Apple Silicon
]
SEARCH_DIRS = [HOME_DIR] + ADDITIONAL_SEARCH_DIRS
OUTPUT_FILE = "infected_packages_report.json"
SCAN_BUN_FILES_CONTENT = True  # If True, also search inside bun files for infected package names

# === STEP 1: Parse and normalize CSV ===
def load_infected(csv_path: str) -> dict[str, list[str]]:
    pkgs: dict[str, list[str]] = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        # The CSV is messy; use DictReader and normalize
        reader = csv.DictReader(f)
        for row in reader:
            pkg = (row.get("Package", "") or "").strip().replace("\\", "")
            versions_raw = (row.get("Version", "") or "").strip()
            if not pkg:
                continue
            # Normalize versions: remove '=', split by whitespace/newlines
            parts = [v.replace("=", "").strip() for v in versions_raw.split() if v.strip()]
            # Deduplicate while preserving order
            seen = set()
            versions = []
            for v in parts:
                if v and v not in seen:
                    seen.add(v)
                    versions.append(v)
            pkgs[pkg] = versions if versions else ["unknown"]
    return pkgs

infected_packages = load_infected(CSV_FILE)
print(f"👀 Read information (names and versions) about {len(infected_packages)} infected packages.")

# === STEP 2: Prepare report ===
report = {"matches": []}

def add_match(file_path: str, package: str, version: str, kind: str, extra: Optional[dict] = None):
    entry = {"file": file_path, "package": package, "version": version, "kind": kind}
    if extra:
        entry.update(extra)
    report["matches"].append(entry)

# === Helper: Check lockfiles ===
def check_lockfiles(project_dir: str):
    package_lock = os.path.join(project_dir, "package-lock.json")
    yarn_lock = os.path.join(project_dir, "yarn.lock")
    pnpm_lock = os.path.join(project_dir, "pnpm-lock.yaml")

    # package-lock.json — use jq when available
    if os.path.isfile(package_lock):
        for pkg, versions in infected_packages.items():
            for ver in versions:
                try:
                    result = subprocess.run(
                        ["jq", f".dependencies[\"{pkg}\"]?.version == \"{ver}\"", package_lock],
                        capture_output=True, text=True
                    )
                    if "true" in result.stdout:
                        add_match(package_lock, pkg, ver, kind="package-lock.json")
                except Exception:
                    # Fallback: string search (less accurate)
                    try:
                        with open(package_lock, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            if f"\"{pkg}\": {{\"version\": \"{ver}\"" in content or f"\"version\": \"{ver}\"" in content and f"\"{pkg}\"" in content:
                                add_match(package_lock, pkg, ver, kind="package-lock.json-fallback")
                    except Exception:
                        pass

    # yarn.lock
    if os.path.isfile(yarn_lock):
        try:
            with open(yarn_lock, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for pkg, versions in infected_packages.items():
                    for ver in versions:
                        if f"\"{pkg}@{ver}\"" in content or f"{pkg}@{ver}" in content:
                            add_match(yarn_lock, pkg, ver, kind="yarn.lock")
        except Exception:
            pass

    # pnpm-lock.yaml
    if os.path.isfile(pnpm_lock):
        try:
            with open(pnpm_lock, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for pkg, versions in infected_packages.items():
                    for ver in versions:
                        # pnpm lock can appear like /pkg@ver: or specifiers under packages: section
                        if f"/{pkg}@{ver}:" in content or f"{pkg}:{ver}" in content:
                            add_match(pnpm_lock, pkg, ver, kind="pnpm-lock.yaml")
        except Exception:
            pass

# === Helper: Check bun-related files ===
BUN_FILENAMES = {"setup_bun.js", "bun_environment.js"}

def scan_bun_files(project_dir: str):
    for fname in BUN_FILENAMES:
        fpath = os.path.join(project_dir, fname)
        if os.path.isfile(fpath):
            # Report presence
            add_match(fpath, package="(bun file)", version="n/a", kind="bun-file-present")
            if SCAN_BUN_FILES_CONTENT:
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        # naive search for package names; catches import/require/specifier mentions
                        for pkg in infected_packages.keys():
                            if pkg in content:
                                add_match(fpath, package=pkg, version="unknown", kind="bun-file-content-hit")
                except Exception:
                    pass

# === STEP 3: Scan local projects ===
for search_dir in SEARCH_DIRS:
    if not os.path.exists(search_dir):
        print(f"⚠️ Skipping non-existent directory: {search_dir}")
        continue

    print(f"🔍 Scanning: {search_dir}")
    for root, dirs, files in os.walk(search_dir):
        # Skip some heavy directories for speed (optional)
        # if any(x in root for x in ["/.git/", "/.cache/"]): continue

        # bun files at project root
        scan_bun_files(root)

        if "package.json" in files:
            check_lockfiles(root)

        if "node_modules" in dirs:
            nm_path = os.path.join(root, "node_modules")
            for pkg in infected_packages.keys():
                pkg_dir = os.path.join(nm_path, pkg)
                if os.path.isdir(pkg_dir):
                    # Try to read installed version from package.json if present
                    installed_ver = "unknown"
                    pkg_json = os.path.join(pkg_dir, "package.json")
                    if os.path.isfile(pkg_json):
                        try:
                            result = subprocess.run(
                                ["jq", "-r", ".version"], input=open(pkg_json, "r", encoding="utf-8").read(),
                                capture_output=True, text=True
                            )
                            val = result.stdout.strip()
                            if val:
                                installed_ver = val
                        except Exception:
                            try:
                                # fallback to quick parse
                                with open(pkg_json, "r", encoding="utf-8", errors="ignore") as f:
                                    txt = f.read()
                                    # very naive parse
                                    import re
                                    m = re.search(r'"version"\s*:\s*"([^"]+)"', txt)
                                    if m:
                                        installed_ver = m.group(1)
                            except Exception:
                                pass
                    add_match(nm_path, pkg, installed_ver, kind="node_modules")

# === STEP 4: Scan global npm installs ===
try:
    global_npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    if os.path.isdir(global_npm_root):
        for pkg in infected_packages.keys():
            pkg_dir = os.path.join(global_npm_root, pkg)
            if os.path.isdir(pkg_dir):
                add_match(global_npm_root, pkg, "global", kind="global-node_modules")
except Exception:
    pass

# === STEP 5: Scan nvm installations ===
nvm_dir = os.path.join(HOME_DIR, ".nvm", "versions", "node")
if os.path.isdir(nvm_dir):
    for root, dirs, files in os.walk(nvm_dir):
        # bun files could also live inside project dirs under nvm; scan them too
        scan_bun_files(root)
        if "node_modules" in dirs:
            nm_path = os.path.join(root, "node_modules")
            for pkg in infected_packages.keys():
                if os.path.isdir(os.path.join(nm_path, pkg)):
                    add_match(nm_path, pkg, "nvm", kind="nvm-node_modules")

# === STEP 6: Scan npm cache ===
try:
    npm_cache = subprocess.run(["npm", "config", "get", "cache"], capture_output=True, text=True).stdout.strip()
    if os.path.isdir(npm_cache):
        for pkg in infected_packages.keys():
            for file in Path(npm_cache).rglob(f"{pkg}-*.tgz"):
                add_match(str(file), pkg, "cached", kind="npm-cache-tarball")
except Exception:
    pass

# === STEP 7: Save report ===
with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
    json.dump(report, out, indent=2)

print(f"✅ Scan complete. Found {len(report['matches'])} findings. Report saved to {OUTPUT_FILE}.")
