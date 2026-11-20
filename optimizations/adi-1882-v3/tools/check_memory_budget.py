"""Report a linked Windows FP32 reference image; never an ADI map substitute."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def inspect(path, stack_bytes, budget_bytes, io_bytes=2048):
    data = path.read_bytes()
    pe = struct.unpack_from('<I', data, 60)[0]
    if data[pe:pe + 4] != b'PE\0\0':
        raise ValueError('Expected a PE image')
    count = struct.unpack_from('<H', data, pe + 6)[0]
    optional = struct.unpack_from('<H', data, pe + 20)[0]
    sections = {}
    writable = 0
    readonly = 0
    code = 0
    for index in range(count):
        at = pe + 24 + optional + 40 * index
        name = data[at:at + 8].rstrip(b'\0').decode('ascii')
        size, = struct.unpack_from('<I', data, at + 8)
        flags, = struct.unpack_from('<I', data, at + 36)
        sections[name] = size
        if flags & 0x80000000:
            writable += size
        elif flags & 0x20000000:
            code += size
        else:
            readonly += size
    return dict(
        evidence='MSVC x64 FP32 linked sections, not CCES or stack high-water',
        sha256=hashlib.sha256(data).hexdigest(), sections_bytes=sections,
        writable_static_bytes=writable, reserved_stack_bytes=stack_bytes,
        algorithm_ram_plus_reserved_stack_bytes=writable + stack_bytes + io_bytes,
        caller_stereo_output_bytes=io_bytes,
        conservative_ram_plus_reserved_stack_bytes=writable + readonly + stack_bytes + io_bytes,
        readonly_sections_bytes=readonly, code_bytes=code,
        all_sections_plus_reserved_stack_bytes=sum(sections.values()) + stack_bytes + io_bytes,
        budget_bytes=budget_bytes, margin_bytes=budget_bytes - writable - readonly - stack_bytes - io_bytes,
        pass_ram_budget=writable + readonly + stack_bytes + io_bytes <= budget_bytes,
        scope='Budget gate includes every writable and read-only non-code DLL section, '
              'retained startup pools, a 64KiB stack reservation and a 2KiB caller stereo '
              'output buffer. It conservatively '
              'counts constants and PE metadata as RAM. Excludes test executable, '
              'OS process, firmware DMA/I/O buffers, cache and code; target map and '
              'target stack high-water remain required.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--stack-bytes', type=int, default=65536)
    parser.add_argument('--budget-bytes', type=int, default=600000)
    parser.add_argument('--io-bytes', type=int, default=2048,
                        help='256-frame stereo float output; input/firmware DMA excluded')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = inspect(args.image, args.stack_bytes, args.budget_bytes, args.io_bytes)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text + '\n', encoding='utf-8')
    return 0 if result['pass_ram_budget'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
