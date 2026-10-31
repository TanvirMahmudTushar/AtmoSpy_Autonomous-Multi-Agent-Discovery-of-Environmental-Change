"""Pack built cubes into one zip file each, for hosting as plain downloads.

    cd backend
    python -m scripts.pack_cubes                     # data/cubes -> data/cubes_release
    gh release create data-v1 ../data/cubes_release/* --title "Data cubes v1"

A Zarr directory is hundreds of small chunk files; most file hosts (GitHub
release assets, simple buckets) want a handful of large ones. Each cube is
zipped without recompression (its chunks are already compressed), and the
copied manifest.json gets "store": "<code>.zarr.zip" so the app reads the
zip. Then set CUBE_BASE_URL to the folder the files are served from, e.g.
https://github.com/<owner>/<repo>/releases/download/data-v1
"""

import argparse
import json
import sys
import zipfile
from pathlib import Path

from app.nasa.cube import DEFAULT_CUBE_DIR, MANIFEST


def pack(src: Path, out: Path) -> list[Path]:
    manifest = json.loads((src / MANIFEST).read_text())
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for code in sorted(manifest):
        store = src / f"{code}.zarr"
        if not store.is_dir():
            print(f"{code}: no {store.name}, skipped")
            continue
        target = out / f"{code}.zarr.zip"
        tmp = target.with_suffix(".zip.tmp")
        # Zarr keys are paths relative to the store root, always with "/".
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
            for f in sorted(p for p in store.rglob("*") if p.is_file()):
                z.write(f, f.relative_to(store).as_posix())
        tmp.replace(target)
        manifest[code] = {**manifest[code], "store": target.name}
        written.append(target)
        print(f"{code}: {target.name} ({target.stat().st_size / 1e6:.0f} MB)")
    (out / MANIFEST).write_text(json.dumps(manifest, indent=2))
    written.append(out / MANIFEST)
    return written


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", type=Path, default=DEFAULT_CUBE_DIR)
    p.add_argument("--out", type=Path, default=DEFAULT_CUBE_DIR.parent / "cubes_release")
    args = p.parse_args(argv)
    pack(args.src, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
