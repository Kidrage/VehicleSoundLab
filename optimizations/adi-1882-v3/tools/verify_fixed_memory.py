"""Compare the fixed V10 memory build with its frozen static audio baseline.

The renderer owns the identical 200 Hz input timeline. This script compares
float PCM, every native stem, and driver/event telemetry; host timing is
reported separately and must not be interpreted as ADI MCPS or peak budget.
Requires NumPy for bounded, fast inspection of the saved float streams.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import struct
import subprocess
import sys
import time

import numpy as np

SCENES = (
    ("startup", 6), ("idle", 3), ("acceleration", 10), ("cruise", 3),
    ("high", 3), ("lift", 8), ("brake", 6), ("shift", 10), ("stop", 6),
    ("full", 36), ("restart", 14), ("events", 3),
)
STEM_CHANNELS = (
    "dna.L", "dna.R", "low.L", "low.R", "detail.L", "detail.R",
    "intake", "mechanical", "exhaust_air.L", "exhaust_air.R", "road", "wind",
    "startup.L", "startup.R", "catch.L", "catch.R", "added.L", "added.R",
    "legacy_event", "event_0", "event_1", "event_2", "event_3",
)
AUDIO_ENV = ("VSL_AIR", "VSL_AIR_SWEEP", "VSL_LINE", "VSL_MECHANICAL", "VSL_PERF_FILE")
TIMING_FIELDS = {"seconds", "thread_cycles"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def wave_data(path: Path) -> tuple[int, int, dict]:
    """Locate IEEE float WAV data without depending on PCM-only wave readers."""
    fmt = None
    data = None
    with path.open("rb") as source:
        header = source.read(12)
        if len(header) != 12 or header[:4] != b"RIFF" or header[8:] != b"WAVE":
            raise ValueError(f"not a RIFF WAV: {path}")
        while chunk := source.read(8):
            if len(chunk) != 8:
                raise ValueError(f"truncated chunk: {path}")
            name, count = struct.unpack("<4sI", chunk)
            offset = source.tell()
            if name == b"fmt ":
                raw = source.read(min(count, 40))
                if len(raw) < 16:
                    raise ValueError(f"truncated fmt: {path}")
                code, channels, rate, byte_rate, align, bits = struct.unpack("<HHIIHH", raw[:16])
                fmt = dict(format=code, channels=channels, rate=rate, byte_rate=byte_rate,
                           block_align=align, bits=bits)
            elif name == b"data":
                data = (offset, count)
            source.seek(offset + count + (count & 1))
    if fmt is None or data is None or (fmt["format"], fmt["channels"], fmt["rate"], fmt["bits"]) != (3, 2, 48000, 32):
        raise ValueError(f"expected 48k stereo FP32 WAV: {path}")
    if data[0] + data[1] > path.stat().st_size or data[1] % 8:
        raise ValueError(f"truncated/unaligned PCM payload: {path}")
    return *data, fmt


def compare_floats(before: Path, after: Path, channels: tuple[str, ...], wav: bool = False) -> dict:
    """Read fixed-size chunks; channel hashes preserve signed-zero/bit identity."""
    if wav:
        offset_a, bytes_a, fmt_a = wave_data(before)
        offset_b, bytes_b, fmt_b = wave_data(after)
        metadata_equal = fmt_a == fmt_b
    else:
        offset_a = offset_b = 0
        bytes_a, bytes_b = before.stat().st_size, after.stat().st_size
        metadata_equal = True
    width = len(channels)
    if bytes_a != bytes_b or bytes_a % (4 * width):
        raise ValueError(f"float stream size mismatch: {before} ({bytes_a}) / {after} ({bytes_b})")
    hashes_a = [hashlib.sha256() for _ in channels]
    hashes_b = [hashlib.sha256() for _ in channels]
    whole_a, whole_b = hashlib.sha256(), hashlib.sha256()
    maximum = np.zeros(width)
    peak_a, peak_b = np.zeros(width), np.zeros(width)
    nonfinite_a, nonfinite_b = np.zeros(width, dtype=np.int64), np.zeros(width, dtype=np.int64)
    bit_differences = np.zeros(width, dtype=np.int64)
    remaining = bytes_a
    with before.open("rb") as a, after.open("rb") as b:
        a.seek(offset_a)
        b.seek(offset_b)
        while remaining:
            size = min(remaining, 16384 * width * 4)
            raw_a, raw_b = a.read(size), b.read(size)
            if len(raw_a) != size or len(raw_b) != size:
                raise ValueError("unexpected EOF in float payload")
            whole_a.update(raw_a)
            whole_b.update(raw_b)
            x = np.frombuffer(raw_a, dtype="<f4").reshape(-1, width)
            y = np.frombuffer(raw_b, dtype="<f4").reshape(-1, width)
            finite_x, finite_y = np.isfinite(x), np.isfinite(y)
            nonfinite_a += (~finite_x).sum(axis=0)
            nonfinite_b += (~finite_y).sum(axis=0)
            peak_a = np.maximum(peak_a, np.max(np.where(finite_x, np.abs(x), 0), axis=0))
            peak_b = np.maximum(peak_b, np.max(np.where(finite_y, np.abs(y), 0), axis=0))
            bit_differences += (x.view("<u4") != y.view("<u4")).sum(axis=0)
            if raw_a != raw_b:
                error = np.abs(x.astype(np.float64) - y.astype(np.float64))
                maximum = np.maximum(maximum, np.max(np.where(finite_x & finite_y, error, 0), axis=0))
            for k in range(width):
                hashes_a[k].update(x[:, k].tobytes())
                hashes_b[k].update(y[:, k].tobytes())
            remaining -= size
    by_channel = [dict(channel=name, exact=hashes_a[k].digest() == hashes_b[k].digest(),
                       sha256_before=hashes_a[k].hexdigest(), sha256_after=hashes_b[k].hexdigest(),
                       bit_differences=int(bit_differences[k]), maximum_error_FS=float(maximum[k]),
                       peak_before_FS=float(peak_a[k]), peak_after_FS=float(peak_b[k]),
                       nonfinite_before=int(nonfinite_a[k]), nonfinite_after=int(nonfinite_b[k]))
                  for k, name in enumerate(channels)]
    return dict(exact=metadata_equal and whole_a.digest() == whole_b.digest(),
                finite=not bool(nonfinite_a.sum() + nonfinite_b.sum()), frames=bytes_a // (4 * width),
                maximum_error_FS=float(maximum.max()),
                payload_sha256_before=whole_a.hexdigest(), payload_sha256_after=whole_b.hexdigest(),
                file_sha256_before=digest(before), file_sha256_after=digest(after), channels=by_channel)


def compare_state(before: Path, after: Path, partitioned: bool) -> dict:
    with before.open(newline="", encoding="utf-8") as source:
        rows_a = list(csv.DictReader(source))
    with after.open(newline="", encoding="utf-8") as source:
        rows_b = list(csv.DictReader(source))
    if not rows_a or not rows_b or rows_a[0].keys() != rows_b[0].keys():
        raise ValueError("missing or incompatible state CSV")
    fields = [key for key in rows_a[0] if key not in TIMING_FIELDS]
    if partitioned:
        fields = [key for key in fields if key not in {"frame", "frames"}]
        a = {int(r["frame"]) + int(r["frames"]): r for r in rows_a}
        b = {int(r["frame"]) + int(r["frames"]): r for r in rows_b}
        endpoints = sorted(a.keys() & b.keys())
        pairs = [(end, a[end], b[end]) for end in endpoints]
        coverage = max(a) == max(b) and max(a) in endpoints
    else:
        pairs = [(i, a, b) for i, (a, b) in enumerate(zip(rows_a, rows_b))]
        coverage = len(rows_a) == len(rows_b)
    differences = [dict(position=position, field=field, before=a[field], after=b[field])
                   for position, a, b in pairs for field in fields if a[field] != b[field]]
    return dict(exact=coverage and not differences, comparison="common frame endpoints" if partitioned else "all rows",
                rows_before=len(rows_a), rows_after=len(rows_b), compared_rows=len(pairs), fields=fields,
                difference_count=len(differences), first_differences=differences[:20],
                sha256_before=digest(before), sha256_after=digest(after))


def render(args, library: Path, scene: str, seconds: int, block: int, path: Path | None,
           overrides: dict[str, str] | None = None) -> dict:
    env = os.environ.copy()
    for key in AUDIO_ENV:
        env.pop(key, None)
    env.update(overrides or {})
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
    command = [str(args.renderer), str(library), scene, str(seconds), str(block),
               str(path) if path else "none", "1" if path else "0"]
    begin = time.perf_counter()
    process = subprocess.run(command, cwd=args.root, env=env, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=300)
    wall = time.perf_counter() - begin
    record = dict(command=command, environment=overrides or {}, returncode=process.returncode,
                  wall_seconds=wall, stdout=process.stdout.strip(), stderr=process.stderr.strip())
    if path:
        Path(str(path) + ".run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    if process.returncode:
        raise RuntimeError(f"renderer failed ({process.returncode}): {scene}, {library}\n{process.stderr}")
    lines = [line for line in process.stdout.splitlines() if line.startswith("{")]
    if not lines:
        raise RuntimeError(f"renderer did not return JSON: {process.stdout}")
    record["measurement"] = json.loads(lines[-1])
    if record["measurement"]["frames"] != seconds * 48000:
        raise RuntimeError("renderer frame count mismatch")
    return record


def remove_modules(path: Path | None) -> None:
    if path:
        Path(str(path) + ".modules.f32").unlink(missing_ok=True)


def comparison(before: Path, after: Path, partitioned: bool = False) -> dict:
    audio = compare_floats(before, after, ("monitor.L", "monitor.R"), wav=True)
    stems = compare_floats(Path(str(before) + ".stems.f32"), Path(str(after) + ".stems.f32"), STEM_CHANNELS)
    state = compare_state(Path(str(before) + ".blocks.csv"), Path(str(after) + ".blocks.csv"), partitioned)
    return dict(passed=audio["exact"] and audio["finite"] and stems["exact"] and stems["finite"] and state["exact"],
                audio=audio, stems=stems, state=state)


def timing_pairs(args) -> dict:
    result = dict(scope="Windows host only; no ADI MCPS, hard realtime peak, or board memory claim", scenes=[])
    for scene, seconds in (("idle", 3), ("startup", 6), ("events", 3)):
        rows = []
        for repeat in range(args.timing_pairs):
            order = ("before", "after") if repeat % 2 == 0 else ("after", "before")
            paired = {}
            for side in order:
                paired[side] = render(args, getattr(args, side), scene, seconds, 256, None)["measurement"]
            old, new = paired["before"], paired["after"]
            rows.append(dict(repeat=repeat + 1, order=list(order), before=old, after=new,
                             process_reduction_percent=100 * (1 - new["process_seconds"] / old["process_seconds"]),
                             thread_cycle_reduction_percent=100 * (1 - new["thread_cycles"] / old["thread_cycles"])))
        result["scenes"].append(dict(scene=scene, audio_seconds=seconds, pairs=rows,
                                     median_process_reduction_percent=statistics.median(r["process_reduction_percent"] for r in rows),
                                     median_thread_cycle_reduction_percent=statistics.median(r["thread_cycle_reduction_percent"] for r in rows)))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("renderer", "before", "after", "root", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--timing-pairs", type=int, default=3, help="alternating host-only pairs per timing scene; 0 skips")
    args = parser.parse_args()
    if not 0 <= args.timing_pairs <= 20:
        parser.error("--timing-pairs must be 0..20")
    for name in ("renderer", "before", "after", "root", "output"):
        setattr(args, name, getattr(args, name).resolve())
    for name in ("renderer", "before", "after"):
        if not getattr(args, name).is_file():
            parser.error(f"--{name} does not exist")
    if not args.root.is_dir():
        parser.error("--root is not a directory")
    args.output.mkdir(parents=True, exist_ok=True)
    receipt = dict(schema=1, created_at=dt.datetime.now(dt.timezone.utc).isoformat(), completed=False, passed=False,
                   scope="Saved PC FP32 output equivalence and host timing; not board MCPS or target linker-map certification",
                   python=sys.version, platform=platform.platform(), sample_rate=48000,
                   renderer=dict(path=str(args.renderer), sha256=digest(args.renderer)),
                   before=dict(path=str(args.before), sha256=digest(args.before)),
                   after=dict(path=str(args.after), sha256=digest(args.after)),
                   root=str(args.root), comparisons=[], failures=[])
    report = args.output / "verification.json"

    def save():
        temporary = report.with_suffix(".tmp")
        temporary.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        temporary.replace(report)

    save()
    jobs = [(scene, scene, seconds, {}) for scene, seconds in SCENES]
    jobs += [("air_sweep", "full", 20, {"VSL_AIR_SWEEP": "1"}),
             ("air_zero", "full", 20, {"VSL_AIR": "0"})]
    for name, scene, seconds, overrides in jobs:
        before = args.output / name / "before_256.wav"
        after = args.output / name / "after_256.wav"
        row = dict(name=name, scene=scene, seconds=seconds, block=256, environment=overrides)
        try:
            row["before_run"] = render(args, args.before, scene, seconds, 256, before, overrides)
            row["after_run"] = render(args, args.after, scene, seconds, 256, after, overrides)
            row.update(comparison(before, after))
        except Exception as exc:
            row.update(passed=False, error=str(exc))
        finally:
            remove_modules(before)
            remove_modules(after)
        receipt["comparisons"].append(row)
        if not row["passed"]:
            receipt["failures"].append(name)
        save()
        print(f"{name}: {'PASS' if row['passed'] else 'FAIL'}", flush=True)
    for scene, seconds in (("full", 36), ("restart", 14)):
        before = args.output / scene / "after_256.wav"
        after = args.output / scene / "after_73.wav"
        row = dict(name=scene + "_partition_73", scene=scene, seconds=seconds, blocks=[256, 73])
        try:
            row["after_run"] = render(args, args.after, scene, seconds, 73, after)
            row.update(comparison(before, after, partitioned=True))
        except Exception as exc:
            row.update(passed=False, error=str(exc))
        finally:
            remove_modules(after)
        receipt["comparisons"].append(row)
        if not row["passed"]:
            receipt["failures"].append(row["name"])
        save()
        print(f"{row['name']}: {'PASS' if row['passed'] else 'FAIL'}", flush=True)
    if args.timing_pairs:
        try:
            receipt["host_timing"] = timing_pairs(args)
        except Exception as exc:
            receipt["failures"].append("host_timing")
            receipt["host_timing"] = dict(error=str(exc))
    receipt["completed"] = True
    receipt["passed"] = not receipt["failures"]
    save()
    print(json.dumps(dict(passed=receipt["passed"], report=str(report), failures=receipt["failures"])), flush=True)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
