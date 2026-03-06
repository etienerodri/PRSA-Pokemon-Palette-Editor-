import struct
from pathlib import Path

class PaletteManager:

    def __init__(self):
        self.poke_nclr_path = None
        self.pokeobj_nclr_path = None
        self.colors = []
        self.color_start = 40

    def locate_nclr(self, target_dir: Path):
        if not target_dir.exists():
            return None
        potential = list(target_dir.glob('*.NCLR')) + list(target_dir.glob('*.nclr'))
        return potential[0] if potential else None

    def load_palettes(self, poke_dir: Path, pokeobj_dir: Path) -> bool:
        self.poke_nclr_path = self.locate_nclr(poke_dir)
        self.pokeobj_nclr_path = self.locate_nclr(pokeobj_dir)
        if not self.poke_nclr_path or not self.pokeobj_nclr_path:
            return False
        with open(self.poke_nclr_path, 'rb') as f:
            data = f.read()
        self.colors = []
        for i in range(16):
            if self.color_start + i * 2 + 2 > len(data):
                break
            bgr555 = struct.unpack('<H', data[self.color_start + i * 2:self.color_start + i * 2 + 2])[0]
            r5 = bgr555 & 31
            g5 = bgr555 >> 5 & 31
            b5 = bgr555 >> 10 & 31
            r8 = r5 << 3 | r5 >> 2
            g8 = g5 << 3 | g5 >> 2
            b8 = b5 << 3 | b5 >> 2
            self.colors.append((r8, g8, b8))
        return True

    def get_hex_colors(self) -> list[str]:
        return [f'#{r:02X}{g:02X}{b:02X}' for r, g, b in self.colors]

    def update_color(self, index: int, r: int, g: int, b: int):
        if 0 <= index < len(self.colors):
            self.colors[index] = (r, g, b)
            self.save_palettes()

    def save_palettes(self):
        if not self.poke_nclr_path or not self.pokeobj_nclr_path:
            return
        color_bytes = bytearray()
        for r, g, b in self.colors:
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            r5 = (r * 31 + 127) // 255
            g5 = (g * 31 + 127) // 255
            b5 = (b * 31 + 127) // 255
            bgr555 = r5 | g5 << 5 | b5 << 10
            color_bytes.extend(struct.pack('<H', bgr555))
        if self.poke_nclr_path.exists():
            with open(self.poke_nclr_path, 'rb') as f:
                poke_data = bytearray(f.read())
            poke_data[self.color_start:self.color_start + len(color_bytes)] = color_bytes
            with open(self.poke_nclr_path, 'wb') as f:
                f.write(poke_data)
        if self.pokeobj_nclr_path.exists():
            with open(self.pokeobj_nclr_path, 'rb') as f:
                pokeobj_data = bytearray(f.read())
            pokeobj_data[self.color_start:self.color_start + len(color_bytes)] = color_bytes
            with open(self.pokeobj_nclr_path, 'wb') as f:
                f.write(pokeobj_data)
