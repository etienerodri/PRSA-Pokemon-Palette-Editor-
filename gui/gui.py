from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget, QLineEdit, QGridLayout, QGroupBox, QScrollArea
from PyQt6.QtCore import Qt
COLOR_BG_MAIN = '#182d55'
COLOR_ELEMENT_BG = '#26395e'
COLOR_ACCENT = '#6d86a8'
COLOR_HOVER = '#354a75'
COLOR_TEXT = '#FFFFFF'
GLOBAL_STYLE = f'\n    QMainWindow, QWidget {{\n        background-color: {COLOR_BG_MAIN};\n        color: {COLOR_TEXT};\n        font-family: Arial;\n    }}\n    \n    QPushButton {{\n        background-color: {COLOR_ELEMENT_BG};\n        color: {COLOR_TEXT};\n        border: 2px solid {COLOR_ACCENT};\n        border-radius: 8px;\n        font-size: 12px;\n        font-weight: bold;\n        min-height: 35px;\n        padding: 4px 12px;\n    }}\n    QPushButton:hover {{\n        background-color: {COLOR_HOVER};\n    }}\n    QPushButton:disabled {{\n        color: #5a6070;\n        border-color: #3a4560;\n        background-color: {COLOR_ELEMENT_BG};\n    }}\n\n    QGroupBox {{\n        background-color: {COLOR_ELEMENT_BG};\n        border: 2px solid {COLOR_ACCENT};\n        border-radius: 8px;\n        margin-top: 15px;\n        font-weight: bold;\n    }}\n    QGroupBox::title {{\n        subcontrol-origin: margin;\n        subcontrol-position: top left;\n        padding: 0 5px;\n        left: 10px;\n        color: {COLOR_TEXT};\n    }}\n\n    QListWidget, QLineEdit {{\n        background-color: {COLOR_BG_MAIN};\n        color: {COLOR_TEXT};\n        border: 1px solid {COLOR_ACCENT};\n        border-radius: 5px;\n        padding: 4px;\n    }}\n\n    QScrollArea {{\n        background-color: {COLOR_ELEMENT_BG};\n        border: 2px dashed {COLOR_ACCENT};\n        border-radius: 5px;\n    }}\n    QScrollArea > QWidget > QWidget {{\n        background-color: {COLOR_ELEMENT_BG};\n    }}\n\n    QLabel {{\n        background-color: transparent;\n        color: {COLOR_TEXT};\n        font-size: 12px;\n    }}\n'

class PaletteEditorGUI(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Pokémon Ranger Shadows of Almia: Pokémon Palette Editor')
        self.resize(900, 600)
        self.setStyleSheet(GLOBAL_STYLE)
        self.initUI()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        top_bar = QHBoxLayout()
        self.btn_load_rom = QPushButton('Load ROM')
        self.btn_save_rom = QPushButton('Save ROM')
        self.btn_save_rom.setEnabled(False)
        top_bar.addWidget(self.btn_load_rom)
        top_bar.addWidget(self.btn_save_rom)
        top_bar.addStretch()
        main_layout.addLayout(top_bar)
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)
        list_group = QGroupBox('1. Select Pokémon ID')
        list_layout = QVBoxLayout()
        self.pokemon_list = QListWidget()
        list_layout.addWidget(self.pokemon_list)
        list_group.setLayout(list_layout)
        content_layout.addWidget(list_group, 1)
        editor_group = QGroupBox('2. Edit Palette')
        editor_layout = QVBoxLayout()
        self.palette_grid = QGridLayout()
        self.color_buttons = []
        for i in range(16):
            btn = QPushButton()
            btn.setFixedSize(40, 40)
            btn.setProperty('color_index', i)
            btn.setStyleSheet('background-color: #A0A0A0; border: 1px solid #000;')
            self.palette_grid.addWidget(btn, i // 4, i % 4)
            self.color_buttons.append(btn)
        editor_layout.addLayout(self.palette_grid)
        color_tools_layout = QHBoxLayout()
        self.hex_input = QLineEdit()
        self.hex_input.setPlaceholderText('#FFFFFF')
        self.btn_color_wheel = QPushButton('🎨 Color Wheel')
        color_tools_layout.addWidget(QLabel('Hex:'))
        color_tools_layout.addWidget(self.hex_input)
        color_tools_layout.addWidget(self.btn_color_wheel)
        editor_layout.addLayout(color_tools_layout)
        editor_layout.addStretch()
        editor_group.setLayout(editor_layout)
        content_layout.addWidget(editor_group, 1)
        preview_group = QGroupBox('3. Tilesheet Preview')
        preview_layout = QVBoxLayout()
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setMinimumSize(300, 300)
        self.lbl_preview = QLabel('Pokémon Tilesheet Preview\n\n(Waiting for selection...)')
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.lbl_preview)
        preview_layout.addWidget(self.scroll_area)
        nav_layout = QHBoxLayout()
        self.btn_prev_frame = QPushButton('◀ Previous')
        self.lbl_frame_counter = QLabel('Frame: 0 / 0')
        self.lbl_frame_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_next_frame = QPushButton('Next ▶')
        self.btn_prev_frame.setEnabled(False)
        self.btn_next_frame.setEnabled(False)
        nav_layout.addWidget(self.btn_prev_frame)
        nav_layout.addWidget(self.lbl_frame_counter)
        nav_layout.addWidget(self.btn_next_frame)
        preview_layout.addLayout(nav_layout)
        preview_group.setLayout(preview_layout)
        content_layout.addWidget(preview_group, 2)
