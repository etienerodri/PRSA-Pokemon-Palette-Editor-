import struct
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
CRC16_TABLE = [0, 49345, 49537, 320, 49921, 960, 640, 49729, 50689, 1728, 1920, 51009, 1280, 50625, 50305, 1088, 52225, 3264, 3456, 52545, 3840, 53185, 52865, 3648, 2560, 51905, 52097, 2880, 51457, 2496, 2176, 51265, 55297, 6336, 6528, 55617, 6912, 56257, 55937, 6720, 7680, 57025, 57217, 8000, 56577, 7616, 7296, 56385, 5120, 54465, 54657, 5440, 55041, 6080, 5760, 54849, 53761, 4800, 4992, 54081, 4352, 53697, 53377, 4160, 61441, 12480, 12672, 61761, 13056, 62401, 62081, 12864, 13824, 63169, 63361, 14144, 62721, 13760, 13440, 62529, 15360, 64705, 64897, 15680, 65281, 16320, 16000, 65089, 64001, 15040, 15232, 64321, 14592, 63937, 63617, 14400, 10240, 59585, 59777, 10560, 60161, 11200, 10880, 59969, 60929, 11968, 12160, 61249, 11520, 60865, 60545, 11328, 58369, 9408, 9600, 58689, 9984, 59329, 59009, 9792, 8704, 58049, 58241, 9024, 57601, 8640, 8320, 57409, 40961, 24768, 24960, 41281, 25344, 41921, 41601, 25152, 26112, 42689, 42881, 26432, 42241, 26048, 25728, 42049, 27648, 44225, 44417, 27968, 44801, 28608, 28288, 44609, 43521, 27328, 27520, 43841, 26880, 43457, 43137, 26688, 30720, 47297, 47489, 31040, 47873, 31680, 31360, 47681, 48641, 32448, 32640, 48961, 32000, 48577, 48257, 31808, 46081, 29888, 30080, 46401, 30464, 47041, 46721, 30272, 29184, 45761, 45953, 29504, 45313, 29120, 28800, 45121, 20480, 37057, 37249, 20800, 37633, 21440, 21120, 37441, 38401, 22208, 22400, 38721, 21760, 38337, 38017, 21568, 39937, 23744, 23936, 40257, 24320, 40897, 40577, 24128, 23040, 39617, 39809, 23360, 39169, 22976, 22656, 38977, 34817, 18624, 18816, 35137, 19200, 35777, 35457, 19008, 19968, 36545, 36737, 20288, 36097, 19904, 19584, 35905, 17408, 33985, 34177, 17728, 34561, 18368, 18048, 34369, 33281, 17088, 17280, 33601, 16640, 33217, 32897, 16448]

def calculate_crc16(data: bytes) -> int:
    crc = 65535
    for byte in data:
        crc = crc >> 8 & 255 ^ CRC16_TABLE[(crc ^ byte) & 255]
    return crc & 65535

def _align4(value: int) -> int:
    return value + 3 & ~3

@dataclass
class NDSHeader:
    raw_data: bytearray = field(default_factory=lambda: bytearray(512))

    @classmethod
    def from_bytes(cls, data: bytes) -> 'NDSHeader':
        if len(data) < 512:
            raise ValueError(f'Header data too short: {len(data)} < 512 bytes')
        return cls(bytearray(data[:512]))

    def to_bytes(self) -> bytes:
        return bytes(self.raw_data)

    @property
    def game_title_str(self) -> str:
        return self.raw_data[0:12].decode('ascii', errors='ignore').strip('\x00')

    @property
    def filename_table_addr(self) -> int:
        return struct.unpack_from('<I', self.raw_data, 64)[0]

    @property
    def filename_size(self) -> int:
        return struct.unpack_from('<I', self.raw_data, 68)[0]

    @property
    def fat_addr(self) -> int:
        return struct.unpack_from('<I', self.raw_data, 72)[0]

    @property
    def fat_size(self) -> int:
        return struct.unpack_from('<I', self.raw_data, 76)[0]

    @property
    def rom_size(self) -> int:
        return struct.unpack_from('<I', self.raw_data, 128)[0]

    @rom_size.setter
    def rom_size(self, value: int):
        struct.pack_into('<I', self.raw_data, 128, value)

    def update_crc(self):
        crc = calculate_crc16(self.raw_data[:350])
        struct.pack_into('<H', self.raw_data, 350, crc)

@dataclass
class FATEntry:
    start_addr: int
    end_addr: int

    @property
    def size(self) -> int:
        return self.end_addr - self.start_addr

    @classmethod
    def from_bytes(cls, data: bytes) -> 'FATEntry':
        start, end = struct.unpack('<II', data[0:8])
        return cls(start, end)

    def to_bytes(self) -> bytes:
        return struct.pack('<II', self.start_addr, self.end_addr)

@dataclass
class ModificationRecord:
    filename: str
    new_data: bytes
    mod_type: str
    fat_index: int = -1

    @property
    def size(self) -> int:
        return len(self.new_data)

    @property
    def resolved(self) -> bool:
        return self.fat_index >= 0

class ArchiveBuilder:

    @staticmethod
    def decompress_lz10(data: bytes) -> bytes:
        if len(data) < 4 or data[0] != 16:
            return data
        dst_size = data[1] | data[2] << 8 | data[3] << 16
        if dst_size == 0:
            if len(data) >= 8:
                dst_size = struct.unpack_from('<I', data, 4)[0]
                src_i = 8
            else:
                return data
        else:
            src_i = 4
        out = bytearray()
        while len(out) < dst_size and src_i < len(data):
            flags = data[src_i]
            src_i += 1
            for bit in range(7, -1, -1):
                if len(out) >= dst_size or src_i >= len(data):
                    break
                if flags & 1 << bit == 0:
                    out.append(data[src_i])
                    src_i += 1
                else:
                    if src_i + 1 >= len(data):
                        break
                    b1, b2 = (data[src_i], data[src_i + 1])
                    src_i += 2
                    disp = (b1 & 15) << 8 | b2
                    length = (b1 >> 4) + 3
                    copy_pos = len(out) - (disp + 1)
                    for _ in range(length):
                        if copy_pos < 0 or copy_pos >= len(out):
                            out.append(0)
                        else:
                            out.append(out[copy_pos])
                        copy_pos += 1
        return bytes(out)

    @staticmethod
    def compress_lz10(data: bytes) -> bytes:
        n = len(data)
        output = bytearray([16, n & 255, n >> 8 & 255, n >> 16 & 255])
        if n == 0:
            return bytes(output)
        HASH_SIZE = 1 << 15
        head = [-1] * HASH_SIZE
        lru = [-1] * HASH_SIZE

        def hash3(pos):
            if pos + 2 >= n:
                return 0
            return (data[pos] << 16 | data[pos + 1] << 8 | data[pos + 2]) & HASH_SIZE - 1

        def find_best_match(pos):
            if pos + 2 >= n:
                return (0, 0)
            best_len = best_dist = 0
            h = hash3(pos)
            j = head[h]
            checked = 0
            while j >= 0 and checked < 64:
                if pos - j > 4096 or j >= pos:
                    break
                match_len = 0
                limit = min(18, n - pos)
                while match_len < limit and data[j + match_len] == data[pos + match_len]:
                    match_len += 1
                if match_len >= 3 and match_len > best_len:
                    best_len = match_len
                    best_dist = pos - j - 1
                    if best_len == 18:
                        break
                j = lru[j & HASH_SIZE - 1]
                checked += 1
            return (best_len, best_dist)
        for i in range(min(4096, n - 2)):
            h = hash3(i)
            lru[i & HASH_SIZE - 1] = head[h]
            head[h] = i
        pos = 0
        while pos < n:
            block_pos = len(output)
            output.append(0)
            flags = 0
            for bit in range(8):
                if pos >= n:
                    break
                la = pos + 4096
                if la < n - 2:
                    h = hash3(la)
                    lru[la & HASH_SIZE - 1] = head[h]
                    head[h] = la
                best_len, best_dist = find_best_match(pos)
                if best_len >= 3:
                    flags |= 1 << 7 - bit
                    output.append(best_len - 3 << 4 | best_dist >> 8)
                    output.append(best_dist & 255)
                    for skip in range(1, best_len):
                        if pos + skip < n - 2:
                            h = hash3(pos + skip)
                            idx = pos + skip & HASH_SIZE - 1
                            lru[idx] = head[h]
                            head[h] = pos + skip
                    pos += best_len
                else:
                    output.append(data[pos])
                    if pos < n - 2:
                        h = hash3(pos)
                        lru[pos & HASH_SIZE - 1] = head[h]
                        head[h] = pos
                    pos += 1
            output[block_pos] = flags
        return bytes(output)

class ModificationTracker:

    def __init__(self):
        self._mods: Dict[str, ModificationRecord] = {}

    def register(self, filename: str, new_data: bytes, mod_type: str='direct') -> bool:
        filename_lower = filename.lower()
        record = ModificationRecord(filename=filename_lower, new_data=new_data, mod_type=mod_type)
        self._mods[filename_lower] = record
        print(f"[Tracker] Queued '{mod_type}' modification for injection: {filename}")
        return True

    def get_all(self) -> List[ModificationRecord]:
        return list(self._mods.values())

class FNTParser:

    def parse(self, rom_data: bytes, fnt_offset: int, fnt_size: int) -> Dict[str, int]:
        index: Dict[str, int] = {}
        self._walk_dir(rom_data, fnt_offset, fnt_size, dir_id=61440, parent_path='', index=index)
        return index

    def _walk_dir(self, rom: bytes, fnt_base: int, fnt_size: int, dir_id: int, parent_path: str, index: Dict[str, int]):
        dir_num = dir_id & 4095
        dir_entry_offset = fnt_base + dir_num * 8
        if dir_entry_offset + 8 > len(rom):
            return
        entries_rel = struct.unpack_from('<I', rom, dir_entry_offset)[0]
        first_idx = struct.unpack_from('<H', rom, dir_entry_offset + 4)[0]
        pos = fnt_base + entries_rel
        current_file_idx = first_idx
        fnt_end = fnt_base + fnt_size
        while pos < fnt_end and pos < len(rom):
            type_len = rom[pos]
            pos += 1
            if type_len == 0:
                break
            is_subdir = bool(type_len & 128)
            name_len = type_len & 127
            if pos + name_len > len(rom):
                break
            name = rom[pos:pos + name_len].decode('ascii', errors='replace')
            pos += name_len
            full_path = (f'{parent_path}/{name}' if parent_path else name).lower()
            if is_subdir:
                if pos + 2 > len(rom):
                    break
                sub_dir_id = struct.unpack_from('<H', rom, pos)[0]
                pos += 2
                self._walk_dir(rom, fnt_base, fnt_size, sub_dir_id, full_path, index)
            else:
                index[full_path] = current_file_idx
                current_file_idx += 1

class ROMModificationCache:

    def __init__(self):
        self.tracker = ModificationTracker()
        self.original_rom_path: Optional[Path] = None
        self.header: Optional[NDSHeader] = None
        self._fat_index_map: Dict[str, int] = {}

    def initialize(self, rom_path: Path) -> bool:
        self.original_rom_path = rom_path.resolve()
        try:
            with open(self.original_rom_path, 'rb') as f:
                rom_data = f.read()
            self.header = NDSHeader.from_bytes(rom_data[:512])
            parser = FNTParser()
            self._fat_index_map = parser.parse(rom_data, self.header.filename_table_addr, self.header.filename_size)
            print(f'[Cache] ROM Initialized: {self.header.game_title_str} | Indexed {len(self._fat_index_map)} files.')
            return True
        except Exception as e:
            print(f'[Cache] Initialization Failed: {e}')
            return False

    def resolve_fat_index(self, filename: str) -> int:
        target = filename.lower()
        if target.endswith('.lz'):
            target = target[:-3]
        for full_path, idx in self._fat_index_map.items():
            if full_path.endswith(target) or full_path.endswith(f'{target}.lz'):
                return idx
        return -1

class ROMBuilder:

    def __init__(self, cache: ROMModificationCache):
        self.cache = cache

    def build_rom(self, output_path: Path) -> Tuple[bool, str]:
        if not self.cache.original_rom_path or not self.cache.original_rom_path.exists():
            return (False, 'Original ROM is missing. Please re-initialize.')
        mods = self.cache.tracker.get_all()
        if not mods:
            return (False, 'No modifications are queued to save.')
        out_path = output_path.resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            unresolved = []
            for mod in mods:
                mod.fat_index = self.cache.resolve_fat_index(mod.filename)
                if not mod.resolved:
                    unresolved.append(mod.filename)
            if unresolved:
                print(f'[Builder] Warning: Could not find these files in ROM: {unresolved}')
            resolvable = [m for m in mods if m.resolved]
            if not resolvable:
                return (False, "None of the modified files were found in the ROM's FAT table.")
            shutil.copy2(self.cache.original_rom_path, out_path)
            fat_entries = self._load_fat()
            with open(out_path, 'r+b') as rom_file:
                current_rom_end = rom_file.seek(0, 2)
                for mod in resolvable:
                    old_entry = fat_entries[mod.fat_index]
                    if mod.size <= old_entry.size:
                        rom_file.seek(old_entry.start_addr)
                        rom_file.write(mod.new_data)
                        fat_entries[mod.fat_index] = FATEntry(old_entry.start_addr, old_entry.start_addr + mod.size)
                    else:
                        aligned_end = _align4(current_rom_end)
                        if aligned_end > current_rom_end:
                            rom_file.seek(current_rom_end)
                            rom_file.write(b'\xff' * (aligned_end - current_rom_end))
                        rom_file.seek(aligned_end)
                        rom_file.write(mod.new_data)
                        fat_entries[mod.fat_index] = FATEntry(aligned_end, aligned_end + mod.size)
                        current_rom_end = aligned_end + mod.size
                fat_raw = bytearray()
                for entry in fat_entries:
                    fat_raw.extend(entry.to_bytes())
                rom_file.seek(self.cache.header.fat_addr)
                rom_file.write(fat_raw)
                self.cache.header.rom_size = current_rom_end
                self.cache.header.update_crc()
                rom_file.seek(0)
                rom_file.write(self.cache.header.to_bytes())
            return (True, f'Successfully built ROM patching {len(resolvable)} file(s).\nSaved to: {out_path.name}')
        except Exception as e:
            import traceback
            traceback.print_exc()
            return (False, f'Failed to build ROM: {e}')

    def _load_fat(self) -> List[FATEntry]:
        with open(self.cache.original_rom_path, 'rb') as f:
            f.seek(self.cache.header.fat_addr)
            fat_raw = f.read(self.cache.header.fat_size)
        entries = []
        for i in range(0, len(fat_raw), 8):
            if i + 8 <= len(fat_raw):
                entries.append(FATEntry.from_bytes(fat_raw[i:i + 8]))
        return entries

class RomSaver:

    def __init__(self, original_rom_path: Path):
        self.cache = ROMModificationCache()
        self.builder = ROMBuilder(self.cache)
        self.cache.initialize(original_rom_path)

    def queue_file(self, filename: str, data: bytes):
        self.cache.tracker.register(filename, data, mod_type='poke_file')

    def patch_and_queue_archive(self, archive_name: str, raw_archive_path: Path, new_nclr_path: Path) -> bool:
        if not raw_archive_path.exists() or not new_nclr_path.exists():
            print(f'[RomSaver] Error: Cannot find paths for {archive_name}')
            return False
        with open(raw_archive_path, 'rb') as f:
            original_data = f.read()
        is_compressed = original_data.startswith(b'\x10')
        decompressed = ArchiveBuilder.decompress_lz10(original_data) if is_compressed else original_data
        with open(new_nclr_path, 'rb') as f:
            new_nclr = f.read()
        nclr_idx = decompressed.find(b'RLCN')
        if nclr_idx == -1:
            nclr_idx = decompressed.find(b'NCLR')
        if nclr_idx != -1:
            patched = bytearray(decompressed)
            patched[nclr_idx:nclr_idx + len(new_nclr)] = new_nclr
            final_data = bytes(patched)
            if is_compressed:
                final_data = ArchiveBuilder.compress_lz10(final_data)
            self.queue_file(archive_name, final_data)
            return True
        else:
            print(f'[RomSaver] Warning: No RLCN/NCLR block found inside {archive_name}')
            return False

    def save_rom(self, output_path: Path) -> Tuple[bool, str]:
        return self.builder.build_rom(output_path)
