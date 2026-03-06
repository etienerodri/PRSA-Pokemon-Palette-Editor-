import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox, QColorDialog
from PyQt6.QtCore import Qt
from gui.gui import PaletteEditorGUI
from gui.pokemonlist import POKEMON_NAMES
from load.romextractor import ExtractionWorker, unpack_file_on_demand
from load.pokepairs import PokePairManager
from load.pokeviewer import PokeViewer
from load.paletteeditor import PaletteManager
from load.saverom import RomSaver

class MainApp:

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.window = PaletteEditorGUI()
        self.original_rom_path = None
        self.pokemon_pairs = []
        self.out_dir = ''
        self.current_pair = None
        self.current_frames = []
        self.current_frame_index = 0
        self.palette_manager = PaletteManager()
        self.active_color_index = 0
        self.window.btn_load_rom.clicked.connect(self.handle_load_rom)
        self.window.btn_save_rom.clicked.connect(self.handle_save_rom)
        self.window.pokemon_list.itemSelectionChanged.connect(self.on_pokemon_selected)
        self.window.btn_prev_frame.clicked.connect(self.show_prev_frame)
        self.window.btn_next_frame.clicked.connect(self.show_next_frame)
        for btn in self.window.color_buttons:
            btn.clicked.connect(self.on_color_button_clicked)
        self.window.btn_color_wheel.clicked.connect(self.on_color_wheel_clicked)
        self.window.hex_input.editingFinished.connect(self.on_hex_input_changed)
        self.window.hex_input.returnPressed.connect(self.on_hex_input_changed)

    def handle_load_rom(self):
        rom_path, _ = QFileDialog.getOpenFileName(self.window, 'Select Pokémon Ranger: Shadows of Almia ROM', '', 'NDS ROM (*.nds);;All files (*.*)')
        if not rom_path:
            return
        self.original_rom_path = Path(rom_path)
        self.out_dir = self.original_rom_path.parent / f'{self.original_rom_path.stem}_extracted'
        self.window.btn_load_rom.setEnabled(False)
        self.window.btn_load_rom.setText('EXTRACTING... PLEASE WAIT')
        self.window.pokemon_list.clear()
        self.window.pokemon_list.addItem('Starting extraction...')
        self.worker = ExtractionWorker(rom_path, str(self.out_dir))
        self.worker.progress.connect(self.on_extraction_progress)
        self.worker.finished.connect(self.on_extraction_success)
        self.worker.error.connect(self.on_extraction_error)
        self.worker.start()

    def on_extraction_progress(self, message):
        if self.window.pokemon_list.count() > 0:
            self.window.pokemon_list.item(0).setText(message)

    def on_extraction_success(self, message):
        self.window.btn_load_rom.setEnabled(True)
        self.window.btn_load_rom.setText('Load ROM')
        self.window.pokemon_list.clear()
        manager = PokePairManager(self.out_dir)
        self.pokemon_pairs = manager.find_pairs()
        if not self.pokemon_pairs:
            QMessageBox.warning(self.window, 'No Pokémon Found', "Extraction finished, but no matching 'poke' and 'pokeobj' pairs were found.")
            return
        for pair in self.pokemon_pairs:
            poke_name = POKEMON_NAMES.get(pair.pokemon_id, 'Unknown Pokémon')
            display_string = f'{pair.pokemon_id} - {poke_name}'
            self.window.pokemon_list.addItem(display_string)
        self.window.btn_save_rom.setEnabled(True)
        QMessageBox.information(self.window, 'Extraction Complete', f'{message}\nSuccessfully paired {len(self.pokemon_pairs)} Pokémon!')

    def on_extraction_error(self, message):
        self.window.btn_load_rom.setEnabled(True)
        self.window.btn_load_rom.setText('Load ROM')
        self.window.pokemon_list.clear()
        QMessageBox.critical(self.window, 'Extraction Failed', f'An error occurred:\n{message}')

    def on_pokemon_selected(self):
        selected_items = self.window.pokemon_list.selectedItems()
        if not selected_items:
            return
        display_text = selected_items[0].text()
        poke_id = display_text.split(' - ')[0]
        pair = next((p for p in self.pokemon_pairs if p.pokemon_id == poke_id), None)
        if not pair:
            return
        self.current_pair = pair
        self.window.lbl_preview.setText(f'Unpacking data for {poke_id}... please wait.')
        self.window.pokemon_list.setEnabled(False)
        QApplication.processEvents()
        try:
            unpack_file_on_demand(pair.poke_raw_path, pair.poke_unpacked_path)
            unpack_file_on_demand(pair.pokeobj_raw_path, pair.pokeobj_unpacked_path)
        except Exception as e:
            QMessageBox.critical(self.window, 'Unpack Error', f'Failed to unpack ID {poke_id}:\n{str(e)}')
            self.window.lbl_preview.setText('Unpack failed.')
            self.window.pokemon_list.setEnabled(True)
            return
        self.window.pokemon_list.setEnabled(True)
        success = self.palette_manager.load_palettes(pair.poke_unpacked_path, pair.pokeobj_unpacked_path)
        if success:
            self.active_color_index = 0
            self.update_palette_ui()
        self.current_frame_index = 0
        self.reload_sprite_preview()

    def on_color_button_clicked(self):
        btn = self.window.sender()
        self.active_color_index = btn.property('color_index')
        self.update_palette_ui()

    def update_palette_ui(self):
        hex_colors = self.palette_manager.get_hex_colors()
        if not hex_colors:
            return
        for i, hex_c in enumerate(hex_colors):
            border = '3px solid red' if i == self.active_color_index else '1px solid #000'
            self.window.color_buttons[i].setStyleSheet(f'background-color: {hex_c}; border: {border};')
        self.window.hex_input.setText(hex_colors[self.active_color_index])

    def on_color_wheel_clicked(self):
        color = QColorDialog.getColor()
        if color.isValid():
            hex_val = color.name().upper()
            self.window.hex_input.setText(hex_val)
            self.apply_color_change(hex_val)

    def on_hex_input_changed(self):
        hex_str = self.window.hex_input.text().upper()
        self.apply_color_change(hex_str)

    def apply_color_change(self, hex_str: str):
        if not hex_str.startswith('#') or len(hex_str) != 7:
            return
        try:
            r = int(hex_str[1:3], 16)
            g = int(hex_str[3:5], 16)
            b = int(hex_str[5:7], 16)
        except ValueError:
            return
        self.palette_manager.update_color(self.active_color_index, r, g, b)
        self.update_palette_ui()
        self.reload_sprite_preview()

    def reload_sprite_preview(self):
        if not self.current_pair:
            return
        viewer = PokeViewer(self.current_pair.poke_unpacked_path, self.current_pair.pokeobj_unpacked_path)
        self.current_frames = viewer.load_sprite_frames()
        if self.current_frames:
            self.update_preview_image()
        else:
            self.window.lbl_preview.setText('Failed to load sprite data.')
            self.window.lbl_frame_counter.setText('Frame: 0 / 0')
            self.window.btn_prev_frame.setEnabled(False)
            self.window.btn_next_frame.setEnabled(False)

    def update_preview_image(self):
        if self.current_frames:
            pixmap = self.current_frames[self.current_frame_index]
            self.window.lbl_preview.setPixmap(pixmap)
            total_frames = len(self.current_frames)
            frame_label = 'Frame: 1 (PokeObj) ' if self.current_frame_index == 0 else f'Frame: {self.current_frame_index + 1} '
            self.window.lbl_frame_counter.setText(f'{frame_label}/ {total_frames}')
            self.window.btn_prev_frame.setEnabled(self.current_frame_index > 0)
            self.window.btn_next_frame.setEnabled(self.current_frame_index < total_frames - 1)

    def show_prev_frame(self):
        if self.current_frame_index > 0:
            self.current_frame_index -= 1
            self.update_preview_image()

    def show_next_frame(self):
        if self.current_frame_index < len(self.current_frames) - 1:
            self.current_frame_index += 1
            self.update_preview_image()

    def handle_save_rom(self):
        if not self.original_rom_path or not self.original_rom_path.exists():
            QMessageBox.warning(self.window, 'Error', 'Original ROM not found! Please load a ROM first.')
            return
        out_path, _ = QFileDialog.getSaveFileName(self.window, 'Save Modified ROM', '', 'NDS ROM (*.nds)')
        if not out_path:
            return
        self.window.btn_save_rom.setEnabled(False)
        self.window.btn_save_rom.setText('SAVING...')
        QApplication.processEvents()
        try:
            rom_saver = RomSaver(self.original_rom_path)
            for pair in self.pokemon_pairs:
                if pair.poke_unpacked_path.exists():
                    poke_nclr = self.palette_manager.locate_nclr(pair.poke_unpacked_path)
                    if poke_nclr:
                        rom_saver.patch_and_queue_archive(f'poke/{pair.poke_raw_path.name}', pair.poke_raw_path, poke_nclr)
                if pair.pokeobj_unpacked_path.exists():
                    pokeobj_nclr = self.palette_manager.locate_nclr(pair.pokeobj_unpacked_path)
                    if pokeobj_nclr:
                        rom_saver.patch_and_queue_archive(f'pokeobj/{pair.pokeobj_raw_path.name}', pair.pokeobj_raw_path, pokeobj_nclr)
            success, msg = rom_saver.save_rom(Path(out_path))
            if success:
                QMessageBox.information(self.window, 'Success', msg)
            else:
                QMessageBox.critical(self.window, 'Save Failed', msg)
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self.window, 'Error', f'Failed to save ROM:\n{str(e)}')
        finally:
            self.window.btn_save_rom.setEnabled(True)
            self.window.btn_save_rom.setText('Save ROM')

    def run(self):
        self.window.show()
        sys.exit(self.app.exec())
if __name__ == '__main__':
    main_app = MainApp()
    main_app.run()
