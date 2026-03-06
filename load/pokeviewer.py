import struct
import math
from pathlib import Path
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

class PokeViewer:

    def __init__(self, poke_dir: Path, pokeobj_dir: Path):
        self.poke_dir = Path(poke_dir)
        self.pokeobj_dir = Path(pokeobj_dir)
        self.frames = []
        print(f"\n[DEBUG] {'=' * 50}")
        print(f'[DEBUG] INITIALIZING RENDERING FOR: {self.poke_dir.name} & {self.pokeobj_dir.name}')
        print(f"[DEBUG] {'=' * 50}")

    def _locate_files(self, target_dir: Path):
        nclr_path = None
        ncbr_paths = []
        if not target_dir.exists():
            return (None, [])
        potential_nclrs = list(target_dir.glob('*.NCLR')) + list(target_dir.glob('*.nclr'))
        if potential_nclrs:
            nclr_path = potential_nclrs[0]
        for p in target_dir.iterdir():
            if p.is_file() and p.suffix.lower() in ['.ncbr', '.ncgr']:
                ncbr_paths.append(p)
        ncbr_paths.sort()
        return (nclr_path, ncbr_paths)

    def load_sprite_frames(self) -> list[QPixmap]:
        self.frames = []
        obj_nclr_path, obj_ncbr_paths = self._locate_files(self.pokeobj_dir)
        if obj_nclr_path and obj_ncbr_paths:
            print(f'[DEBUG] Loading PokeObj First Frame...')
            with open(obj_nclr_path, 'rb') as f:
                obj_palette = self.parse_nclr(f.read())
            with open(obj_ncbr_paths[0], 'rb') as f:
                obj_pixmap = self.parse_pokeobj_ncgr(f.read(), obj_palette)
                if obj_pixmap:
                    self.frames.extend(obj_pixmap)
        poke_nclr_path, poke_ncbr_paths = self._locate_files(self.poke_dir)
        if poke_nclr_path and poke_ncbr_paths:
            print(f'[DEBUG] Loading Poke Animations...')
            with open(poke_nclr_path, 'rb') as f:
                poke_palette = self.parse_nclr(f.read())
            for ncbr_path in poke_ncbr_paths:
                with open(ncbr_path, 'rb') as f:
                    pixmaps = self.parse_ncgr(f.read(), poke_palette)
                    self.frames.extend(pixmaps)
        return self.frames

    def parse_nclr(self, nclr_data: bytes) -> list:
        palette = []
        color_start = 40
        for i in range(16):
            if color_start + i * 2 + 2 > len(nclr_data):
                break
            bgr555 = struct.unpack('<H', nclr_data[color_start + i * 2:color_start + i * 2 + 2])[0]
            r = (bgr555 & 31) << 3
            g = (bgr555 >> 5 & 31) << 3
            b = (bgr555 >> 10 & 31) << 3
            r |= r >> 5
            g |= g >> 5
            b |= b >> 5
            a = 0 if i == 0 else 255
            palette.append((r, g, b, a))
        return palette

    def parse_pokeobj_ncgr(self, ncgr_data: bytes, palette: list) -> list[QPixmap]:
        if len(ncgr_data) < 48:
            return []
        tile_data_size = struct.unpack_from('<I', ncgr_data, 40)[0]
        if tile_data_size == 2048:
            width_px, height_px = (64, 64)
        elif tile_data_size == 512:
            width_px, height_px = (32, 32)
        else:
            print(f'[DEBUG] Unknown PokeObj sprite size: {hex(tile_data_size)}')
            return []
        pixel_data = ncgr_data[48:48 + tile_data_size]
        indices = []
        for byte in pixel_data:
            indices.append(byte & 15)
            indices.append(byte >> 4 & 15)
        img = QImage(width_px, height_px, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        tiles_per_row = width_px // 8
        for tile_idx in range(len(indices) // 64):
            grid_x = tile_idx % tiles_per_row * 8
            grid_y = tile_idx // tiles_per_row * 8
            for p in range(64):
                px_x = p % 8
                px_y = p // 8
                idx = tile_idx * 64 + p
                if idx >= len(indices):
                    break
                color_idx = indices[idx]
                if color_idx != 0 and color_idx < 16 and (color_idx < len(palette)):
                    r, g, b, a = palette[color_idx]
                    argb = a << 24 | r << 16 | g << 8 | b
                    img.setPixel(grid_x + px_x, grid_y + px_y, argb)
        scale_factor = 3
        scaled = img.scaled(img.width() * scale_factor, img.height() * scale_factor, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        return [QPixmap.fromImage(scaled)]

    def parse_ncgr(self, ncgr_data: bytes, palette: list) -> list[QPixmap]:
        if len(ncgr_data) < 48:
            return []
        height_tiles = struct.unpack_from('<H', ncgr_data, 24)[0]
        width_tiles = struct.unpack_from('<H', ncgr_data, 26)[0]
        mapping_flag = struct.unpack_from('<I', ncgr_data, 36)[0]
        is_linear_framebuffer = mapping_flag == 1
        pixel_data_offset = 48
        pixel_data = ncgr_data[pixel_data_offset:]
        width_px = width_tiles * 8
        height_px = height_tiles * 8
        total_tiles = width_tiles * height_tiles
        indices = []
        for byte in pixel_data:
            indices.append(byte & 15)
            indices.append(byte >> 4 & 15)
        img = QImage(width_px, height_px, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        if is_linear_framebuffer:
            for y in range(height_px):
                for x in range(width_px):
                    idx = y * width_px + x
                    if idx >= len(indices):
                        break
                    color_idx = indices[idx]
                    if color_idx != 0 and color_idx < 16 and (color_idx < len(palette)):
                        r, g, b, a = palette[color_idx]
                        argb = a << 24 | r << 16 | g << 8 | b
                        img.setPixel(x, y, argb)
        else:
            for tile_idx in range(total_tiles):
                grid_x = tile_idx % width_tiles * 8
                grid_y = tile_idx // width_tiles * 8
                for p in range(64):
                    px_x = p % 8
                    px_y = p // 8
                    idx = tile_idx * 64 + p
                    if idx >= len(indices):
                        break
                    color_idx = indices[idx]
                    if color_idx != 0 and color_idx < 16 and (color_idx < len(palette)):
                        r, g, b, a = palette[color_idx]
                        argb = a << 24 | r << 16 | g << 8 | b
                        img.setPixel(grid_x + px_x, grid_y + px_y, argb)
        scale_factor = 2 if img.width() > 128 else 4
        scaled = img.scaled(img.width() * scale_factor, img.height() * scale_factor, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        return [QPixmap.fromImage(scaled)]
