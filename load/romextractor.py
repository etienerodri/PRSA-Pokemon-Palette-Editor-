import os
import struct
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

def decompress_lz10(data: bytes) -> bytes:
    if len(data) < 4:
        return data
    if data[0] != 16:
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

def unpack_narc(blob: bytes, out_dir: Path, base_name: str=''):
    out_dir.mkdir(parents=True, exist_ok=True)
    if len(blob) < 16 or blob[0:4] != b'NARC':
        return
    btaf_off = 16
    btaf_size = struct.unpack_from('<I', blob, btaf_off + 4)[0]
    file_count = struct.unpack_from('<I', blob, btaf_off + 8)[0]
    entries = []
    for i in range(file_count):
        start = struct.unpack_from('<I', blob, btaf_off + 12 + i * 8)[0]
        end = struct.unpack_from('<I', blob, btaf_off + 16 + i * 8)[0]
        entries.append((start, end))
    btnf_off = btaf_off + btaf_size
    btnf_size = struct.unpack_from('<I', blob, btnf_off + 4)[0]
    gmif_off = btnf_off + btnf_size
    gmif_data_start = gmif_off + 8
    names = []
    if btnf_size > 16:
        try:
            fnt_start = btnf_off + 8
            root_sub_off = struct.unpack_from('<I', blob, fnt_start)[0]
            curr_off = fnt_start + root_sub_off
            while curr_off < gmif_off and len(names) < file_count:
                type_len = blob[curr_off]
                curr_off += 1
                if type_len == 0:
                    break
                if type_len < 128:
                    name_bytes = blob[curr_off:curr_off + type_len]
                    name = name_bytes.decode('ascii', 'ignore').strip('\x00')
                    names.append(name)
                    curr_off += type_len
                else:
                    name_len = type_len - 128
                    curr_off += name_len
                    curr_off += 2
        except Exception:
            pass
    for i, (start, end) in enumerate(entries):
        file_data = blob[gmif_data_start + start:gmif_data_start + end]
        if not file_data:
            continue
        ext = '.bin'
        if len(file_data) >= 4:
            magic = file_data[0:4]
            if magic == b'RLCN':
                ext = '.NCLR'
            elif magic == b'RGCN':
                ext = '.NCBR'
                if len(file_data) >= 28:
                    grid_w = struct.unpack_from('<H', file_data, 24)[0]
                    grid_h = struct.unpack_from('<H', file_data, 26)[0]
                    if grid_w == 65535 or grid_h == 65535:
                        ext = '.NCGR'
            elif magic == b'RECN':
                ext = '.NCER'
            elif magic == b'RNAN':
                ext = '.NANR'
            elif file_data[0:2] == b'\x0c\x00':
                ext = '.cac'
        if i < len(names) and names[i]:
            file_name = names[i]
            if '.' not in file_name:
                file_name += ext
        else:
            clean_base = base_name.replace('_LZ', '').replace('.bin', '')
            file_name = f'{clean_base}_{i:02d}{ext}'
        file_name = file_name.replace('\x00', '')
        with open(out_dir / file_name, 'wb') as f:
            f.write(file_data)

def unpack_file_on_demand(raw_file_path: Path, output_folder: Path):
    if output_folder.exists() and any(output_folder.iterdir()):
        return
    with open(raw_file_path, 'rb') as f:
        data = f.read()
    if data and data[0] == 16:
        data = decompress_lz10(data)
    if data[0:4] == b'NARC':
        unpack_narc(data, output_folder, raw_file_path.name)
    else:
        output_folder.mkdir(parents=True, exist_ok=True)
        with open(output_folder / raw_file_path.name, 'wb') as f:
            f.write(data)

class ExtractionWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, rom_path: str, out_dir: str):
        super().__init__()
        self.rom_path = Path(rom_path)
        self.out_dir = Path(out_dir)

    def run(self):
        try:
            self.progress.emit('Reading ROM Header...')
            with open(self.rom_path, 'rb') as f:
                rom_data = f.read()
            fnt_offset = struct.unpack_from('<I', rom_data, 64)[0]
            fat_offset = struct.unpack_from('<I', rom_data, 72)[0]
            self.progress.emit('Mapping ROM Filesystem (FNT)...')
            file_paths = self._parse_fnt(rom_data, fnt_offset)
            target_files = {}
            for path, file_id in file_paths.items():
                parts = [p.lower() for p in path.split('/')]
                if 'poke' in parts or 'pokeobj' in parts:
                    target_files[path] = file_id
            total_files = len(target_files)
            if total_files == 0:
                self.error.emit("Could not find 'poke' or 'pokeobj' folders in the ROM.")
                return
            self.progress.emit(f'Found {total_files} archives. Extracting raw files...')
            for i, (path, file_id) in enumerate(target_files.items()):
                self.progress.emit(f"Extracting raw data {i + 1}/{total_files}: {path.split('/')[-1]}")
                fat_entry_offset = fat_offset + file_id * 8
                start_addr = struct.unpack_from('<I', rom_data, fat_entry_offset)[0]
                end_addr = struct.unpack_from('<I', rom_data, fat_entry_offset + 4)[0]
                file_data = rom_data[start_addr:end_addr]
                file_name = path.split('/')[-1]
                parent_dir = [p for p in path.split('/') if p.lower() in ('poke', 'pokeobj')][0]
                out_path = self.out_dir / parent_dir / file_name
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, 'wb') as out_f:
                    out_f.write(file_data)
            self.finished.emit('ROM Extraction Complete! Files ready for on-demand unpacking.')
        except Exception as e:
            self.error.emit(f'Critical Error during extraction: {str(e)}')

    def _parse_fnt(self, rom_data: bytes, fnt_offset: int) -> dict:
        dir_count = struct.unpack_from('<H', rom_data, fnt_offset + 6)[0]
        directories = []
        for i in range(dir_count):
            entry_off = fnt_offset + i * 8
            sub_off = struct.unpack_from('<I', rom_data, entry_off)[0]
            first_file_id = struct.unpack_from('<H', rom_data, entry_off + 4)[0]
            parent_id = struct.unpack_from('<H', rom_data, entry_off + 6)[0]
            directories.append({'sub_off': sub_off, 'first_file_id': first_file_id, 'parent_id': parent_id})
        file_paths = {}
        dir_paths = {0: ''}
        for dir_idx in range(dir_count):
            sub_off = directories[dir_idx]['sub_off']
            file_id = directories[dir_idx]['first_file_id']
            curr_off = fnt_offset + sub_off
            while True:
                type_len = rom_data[curr_off]
                curr_off += 1
                if type_len == 0:
                    break
                if type_len < 128:
                    name = rom_data[curr_off:curr_off + type_len].decode('ascii', 'ignore')
                    curr_off += type_len
                    file_paths[file_id] = (dir_idx, name)
                    file_id += 1
                else:
                    name_len = type_len - 128
                    name = rom_data[curr_off:curr_off + name_len].decode('ascii', 'ignore')
                    curr_off += name_len
                    sub_dir_id = struct.unpack_from('<H', rom_data, curr_off)[0]
                    curr_off += 2
                    sub_dir_idx = sub_dir_id & 4095
                    dir_paths[sub_dir_idx] = (dir_idx, name)
        resolved_dirs = {0: ''}

        def get_dir_path(d_idx):
            if d_idx in resolved_dirs:
                return resolved_dirs[d_idx]
            if d_idx not in dir_paths:
                return ''
            parent_idx, name = dir_paths[d_idx]
            parent_path = get_dir_path(parent_idx)
            path = f'{parent_path}/{name}' if parent_path else name
            resolved_dirs[d_idx] = path
            return path
        final_file_paths = {}
        for f_id, (d_idx, name) in file_paths.items():
            dp = get_dir_path(d_idx)
            full_path = f'{dp}/{name}' if dp else name
            final_file_paths[full_path] = f_id
        return final_file_paths
