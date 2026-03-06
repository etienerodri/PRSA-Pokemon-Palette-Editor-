import re
from pathlib import Path

class PokePair:

    def __init__(self, pokemon_id, poke_raw, pokeobj_raw, poke_unpacked, pokeobj_unpacked):
        self.pokemon_id = pokemon_id
        self.poke_raw_path = Path(poke_raw)
        self.pokeobj_raw_path = Path(pokeobj_raw)
        self.poke_unpacked_path = Path(poke_unpacked)
        self.pokeobj_unpacked_path = Path(pokeobj_unpacked)

class PokePairManager:

    def __init__(self, extracted_dir: str | Path):
        self.extracted_dir = Path(extracted_dir)
        self.poke_dir = self.extracted_dir / 'poke'
        self.pokeobj_dir = self.extracted_dir / 'pokeobj'

    def find_pairs(self) -> list[PokePair]:
        pairs = []
        if not self.poke_dir.exists() or not self.pokeobj_dir.exists():
            return pairs
        for p_file in self.poke_dir.glob('*.bin'):
            match = re.search('p(\\d{3})', p_file.name)
            if match:
                poke_id = match.group(1)
                obj_cands = list(self.pokeobj_dir.glob(f'bp{poke_id}*.bin'))
                if obj_cands:
                    obj_file = obj_cands[0]
                    pairs.append(PokePair(pokemon_id=poke_id, poke_raw=p_file, pokeobj_raw=obj_file, poke_unpacked=self.poke_dir / f'unpacked_{poke_id}', pokeobj_unpacked=self.pokeobj_dir / f'unpacked_{poke_id}'))
        return sorted(pairs, key=lambda x: x.pokemon_id)
