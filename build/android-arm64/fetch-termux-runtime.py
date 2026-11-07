#!/usr/bin/env python3
"""Fetch/extract the current Termux aarch64 Python runtime packages on Ubuntu CI.

This stages Android/Bionic libraries; it never executes Android binaries on the
Ubuntu runner. Dependencies are resolved from Termux's signed repository index.
"""
import bz2, gzip, lzma, pathlib, re, subprocess, sys, urllib.error, urllib.request

BASE = "https://packages.termux.dev/apt/termux-main"
ARCH = "aarch64"
PREFIX = pathlib.Path("out/termux-prefix")
CACHE = pathlib.Path("out/debs")
INDEX_BASE = f"{BASE}/dists/stable/main/binary-{ARCH}/Packages"
CACHE.mkdir(parents=True, exist_ok=True)
PREFIX.mkdir(parents=True, exist_ok=True)

# Termux publishes Packages, Packages.gz and Packages.bz2; Packages.xz is not guaranteed.
raw_bytes = None
last_error = None
for suffix, decoder in (
    (".gz", gzip.decompress),
    (".bz2", bz2.decompress),
    ("", lambda data: data),
    (".xz", lzma.decompress),
):
    index_url = INDEX_BASE + suffix
    try:
        with urllib.request.urlopen(index_url, timeout=60) as response:
            payload = response.read()
        raw_bytes = decoder(payload)
        print(f"Using Termux package index: {index_url}")
        break
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, lzma.LZMAError) as error:
        last_error = error
if raw_bytes is None:
    raise SystemExit(f"Unable to download a supported Termux package index from {INDEX_BASE}: {last_error}")
raw = raw_bytes.decode("utf-8", "replace")

records = {}
for block in raw.split("\n\n"):
    fields = {}
    for line in block.splitlines():
        if line and not line[0].isspace() and ": " in line:
            key, value = line.split(": ", 1)
            fields[key] = value
    if fields.get("Package"):
        records[fields["Package"]] = fields

def dependencies(record):
    result = []
    for item in record.get("Depends", "").split(","):
        # Pick the first alternative; strip architecture/version qualifiers.
        candidate = item.strip().split("|", 1)[0].strip()
        match = re.match(r"([a-z0-9+.-]+)", candidate)
        if match and match.group(1) not in ("apt", "dpkg"):
            result.append(match.group(1))
    return result

wanted = ["python", "python-pycryptodome", "python-pycryptodomex"]
queue, selected = list(wanted), []
while queue:
    name = queue.pop(0)
    if name in selected:
        continue
    record = records.get(name)
    if not record:
        if name in wanted:
            print(f"NOTICE: optional Termux package not found: {name}")
        continue
    selected.append(name)
    queue.extend(dependencies(record))

for name in selected:
    record = records[name]
    filename = record["Filename"]
    url = f"{BASE}/{filename}"
    deb = CACHE / pathlib.Path(filename).name
    if not deb.exists():
        print(f"Downloading {name} {record.get('Version', '')}")
        urllib.request.urlretrieve(url, deb)
    subprocess.run(["dpkg-deb", "-x", str(deb), str(PREFIX)], check=True)

termux_root = PREFIX / "data/data/com.termux/files/usr"
if not termux_root.is_dir():
    raise SystemExit("Termux packages did not contain the expected /data/data/com.termux/files/usr prefix")

# Normalize the Termux absolute prefix into a relocatable prefix for the bundle.
for child in list(termux_root.iterdir()):
    destination = PREFIX / child.name
    if destination.exists():
        subprocess.run(["cp", "-a", str(child) + "/.", str(destination)], check=True)
    else:
        child.rename(destination)

headers = list((PREFIX / "include").glob("python*/Python.h"))
libs = list((PREFIX / "lib").glob("libpython*.so"))
stdlibs = list((PREFIX / "lib").glob("python3.*"))
if not headers or not libs or not stdlibs:
    raise SystemExit("Python runtime package is missing headers, libpython, or stdlib")
print("Staged Termux ARM64 Python runtime:")
print("  header:", headers[0])
print("  shared:", libs[0])
print("  stdlib:", stdlibs[0])
