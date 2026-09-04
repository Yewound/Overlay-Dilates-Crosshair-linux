# -*- coding: utf-8 -*-
# Dilates Crosshair Overlay — merged classic + modern UI
# Both original implementations are preserved below.

import os
import math
os.environ["QT_QPA_PLATFORM"] = "xcb"

import sys
import shutil
import ctypes
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, 
    QVBoxLayout, QHBoxLayout, QSlider, QFrame, QFileDialog, 
    QColorDialog, QGridLayout, QScrollArea,
    QSizePolicy, QComboBox, QFormLayout, QStackedWidget,
    QGraphicsOpacityEffect, QTextEdit
)
from PyQt5.QtCore import Qt, QUrl, QTimer, pyqtSignal, pyqtProperty, QPropertyAnimation, QEasingCurve, QPoint
from PyQt5.QtGui import QPainter, QPen, QColor, QPixmap, QIcon, QDesktopServices, QGuiApplication


class AnimatedToggle(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(46, 24)
        self.setCursor(Qt.PointingHandCursor)
        
        self._circle_position = 3
        self.animation = QPropertyAnimation(self, b"circle_position", self)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setDuration(150)
        
        self.clicked.connect(self.start_animation)

    def get_circle_position(self):
        return self._circle_position

    def set_circle_position(self, pos):
        self._circle_position = pos
        self.update()

    circle_position = pyqtProperty(int, get_circle_position, set_circle_position)

    def start_animation(self, checked):
        if hasattr(self.window(), 'global_anim_mode') and self.window().global_anim_mode == 3:
            self.animation.setDuration(0)
        else:
            self.animation.setDuration(150)

        self.animation.stop()
        if checked:
            self.animation.setStartValue(3)
            self.animation.setEndValue(25)
        else:
            self.animation.setStartValue(25)
            self.animation.setEndValue(3)
        self.animation.start()

    def setChecked(self, checked):
        super().setChecked(checked)
        self._circle_position = 25 if checked else 3
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        
        if self.isChecked():
            bg_color = QColor(self.window().ui_accent_color) if hasattr(self.window(), 'ui_accent_color') else QColor(99, 102, 241)
        else:
            bg_color = QColor(31, 35, 48)
            
        p.setPen(Qt.NoPen)
        p.setBrush(bg_color)
        p.drawRoundedRect(0, 0, 46, 24, 12, 12)
        
        p.setBrush(QColor(255, 255, 255))
        p.drawEllipse(int(self._circle_position), 3, 18, 18)
        p.end()


class CrosshairOverlay(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        
        platform = QGuiApplication.platformName()
        flags = Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool
        
        if platform == 'wayland':
            flags |= Qt.WindowTransparentForInput
        elif platform == 'xcb':
            flags |= Qt.X11BypassWindowManagerHint

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        
        if platform != 'wayland':
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.setFixedSize(screen.size())

        self.anim_tick = 0
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.on_anim_frame)
        self.timer.start()

    def on_anim_frame(self):
        if self.main_window.animation_mode != 'none':
            self.anim_tick += 1
            self.update()

    def apply_x11_input_passthrough(self):
        try:
            if QGuiApplication.platformName() != 'xcb':
                return
            x11 = ctypes.CDLL("libX11.so.6")
            xfixes = ctypes.CDLL("libXfixes.so.3")
            display = x11.XOpenDisplay(None)
            if display:
                window_id = int(self.winId())
                if window_id:
                    region = xfixes.XFixesCreateRegion(display, None, 0)
                    xfixes.XFixesSetWindowShapeRegion(display, window_id, 2, 0, 0, region)
                    xfixes.XFixesDestroyRegion(display, region)
                    x11.XFlush(display)
                x11.XCloseDisplay(display)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        if QGuiApplication.platformName() == 'xcb':
            QTimer.singleShot(50, self.apply_x11_input_passthrough)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        cx = self.width() // 2
        cy = self.height() // 2
        
        size = float(self.main_window.size_val)
        gap = float(self.main_window.gap_val)
        color = self.main_window.color_val
        rotation = float(self.main_window.rotation_val)
        opacity = self.main_window.opacity_val / 100.0
        has_outline = self.main_window.outline_val
        outline_thickness = self.main_window.outline_thickness_val
        
        anim_mode = self.main_window.animation_mode
        anim_speed = self.main_window.animation_speed_val / 10.0
        
        if anim_mode == 'pulse':
            factor = 1.0 + 0.25 * math.sin(self.anim_tick * 0.08 * anim_speed)
            size *= factor
        elif anim_mode == 'spin':
            rotation += (self.anim_tick * 2.0 * anim_speed) % 360
        elif anim_mode == 'breathing':
            alpha_factor = 0.5 + 0.5 * math.sin(self.anim_tick * 0.06 * anim_speed)
            opacity *= max(0.2, alpha_factor)
        elif anim_mode == 'wave':
            gap += abs(6.0 * math.sin(self.anim_tick * 0.1 * anim_speed))
        elif anim_mode == 'rainbow':
            hue = int(self.anim_tick * 3.0 * anim_speed) % 360
            color = QColor.fromHsv(hue, 255, 255)
        elif anim_mode == 'shake':
            amp = 4.0 * anim_speed
            cx += int(amp * math.sin(self.anim_tick * 0.5 * anim_speed))
            cy += int(amp * math.cos(self.anim_tick * 0.7 * anim_speed) * 0.5)
        elif anim_mode == 'flicker':
            import random
            if self.anim_tick % max(1, int(8 / anim_speed)) == 0:
                opacity *= random.uniform(0.1, 1.0)
            else:
                opacity *= 0.85 + 0.15 * math.sin(self.anim_tick * 0.3)
        elif anim_mode == 'orbit':
            orbit_r = size * 0.6
            angle = self.anim_tick * 0.05 * anim_speed
            cx += int(orbit_r * math.cos(angle))
            cy += int(orbit_r * math.sin(angle))

        painter.setOpacity(max(0.0, min(1.0, opacity)))
        
        if self.main_window.selected_builtin.startswith('custom_'):
            pixmap = self.main_window.custom_pixmaps.get(self.main_window.selected_builtin)
            if pixmap and not pixmap.isNull():
                pix = pixmap.scaled(int(size * 4), int(size * 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                if rotation != 0:
                    painter.translate(cx, cy)
                    painter.rotate(rotation)
                    painter.drawPixmap(-pix.width() // 2, -pix.height() // 2, pix)
                else:
                    painter.drawPixmap(cx - pix.width() // 2, cy - pix.height() // 2, pix)
                painter.end()
                return

        base_width = max(1, int(size // 5))
        
        def draw_shapes(p_pen, p_brush_color):
            painter.setPen(p_pen)
            painter.translate(cx, cy)
            painter.rotate(rotation)
            
            ctype = self.main_window.selected_builtin
            if ctype == 'cross':
                painter.setBrush(p_brush_color)
                if gap <= 0:
                    painter.drawLine(int(-size), 0, int(size), 0)
                    painter.drawLine(0, int(-size), 0, int(size))
                else:
                    painter.drawLine(int(-size), 0, int(-gap), 0)
                    painter.drawLine(int(gap), 0, int(size), 0)
                    painter.drawLine(0, int(-size), 0, int(-gap))
                    painter.drawLine(0, int(gap), 0, int(size))
            elif ctype == 'dot':
                painter.setBrush(p_brush_color)
                r = max(2, int(size // 3))
                painter.drawEllipse(-r, -r, r * 2, r * 2)
            elif ctype == 'circle':
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(int(-size), int(-size), int(size * 2), int(size * 2))
            elif ctype == 'cross_circle':
                painter.setBrush(p_brush_color)
                if gap <= 0:
                    painter.drawLine(int(-size), 0, int(size), 0)
                    painter.drawLine(0, int(-size), 0, int(size))
                else:
                    painter.drawLine(int(-size), 0, int(-gap), 0)
                    painter.drawLine(int(gap), 0, int(size), 0)
                    painter.drawLine(0, int(-size), 0, int(-gap))
                    painter.drawLine(0, int(gap), 0, int(size))
                painter.setBrush(Qt.NoBrush)
                r = int(size // 2)
                painter.drawEllipse(-r, -r, r * 2, r * 2)
            elif ctype == 'T-shape':
                painter.setBrush(p_brush_color)
                if gap <= 0:
                    painter.drawLine(int(-size), 0, int(size), 0)
                    painter.drawLine(0, int(-size), 0, 0)
                else:
                    painter.drawLine(int(-size), 0, int(-gap), 0)
                    painter.drawLine(int(gap), 0, int(size), 0)
                    painter.drawLine(0, int(-size), 0, int(-gap))
            elif ctype == 'square':
                painter.setBrush(Qt.NoBrush)
                s = int(size)
                painter.drawRect(-s, -s, s * 2, s * 2)
            elif ctype == 'diamond':
                painter.setBrush(Qt.NoBrush)
                s = int(size)
                painter.save()
                painter.rotate(45)
                painter.drawRect(-s, -s, s * 2, s * 2)
                painter.restore()
            painter.resetTransform()

        if has_outline:
            outline_pen = QPen(QColor(0, 0, 0))
            outline_pen.setWidth(base_width + outline_thickness * 2)
            draw_shapes(outline_pen, QColor(0, 0, 0))

        main_pen = QPen(color)
        main_pen.setWidth(base_width)
        draw_shapes(main_pen, color)
            
        painter.end()


class CrosshairCard(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, ctype, name, icon_pixmap, main_window, parent=None):
        super().__init__(parent)
        self.ctype = ctype
        self.main_window = main_window
        self.is_checked = False
        
        self.setObjectName("CrosshairCardFrame")
        self.setFixedSize(175, 110)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 14, 12, 12)

        self.icon_lbl = QLabel()
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_lbl.setPixmap(icon_pixmap.scaled(70, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(self.icon_lbl, alignment=Qt.AlignHCenter)

        self.text_lbl = QLabel(name)
        self.text_lbl.setAlignment(Qt.AlignCenter)
        self.text_lbl.setStyleSheet("font-weight: 600; font-size: 12px; background: transparent;")
        layout.addWidget(self.text_lbl, alignment=Qt.AlignHCenter)

        self.update_style()

    def setChecked(self, checked):
        self.is_checked = checked
        self.update_style()

    def update_style(self):
        accent = self.main_window.ui_accent_color
        bg = self.main_window.ui_sidebar_color
        main_bg = self.main_window.ui_bg_color
        text_color = self.main_window.ui_text_color
        
        self.text_lbl.setStyleSheet(f"color: {text_color}; font-weight: 600; font-size: 12px; background: transparent;")
        
        r = getattr(self.main_window, 'ui_card_radius', 12)
        if self.is_checked:
            self.setStyleSheet(f"""
                QFrame#CrosshairCardFrame {{
                    background-color: {accent}18;
                    border: 1.5px solid {accent};
                    border-radius: {r}px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#CrosshairCardFrame {{
                    background-color: rgba(255,255,255,0.03);
                    border: 1px solid rgba(255,255,255,0.07);
                    border-radius: {r}px;
                }}
                QFrame#CrosshairCardFrame:hover {{
                    background-color: rgba(255,255,255,0.06);
                    border-color: rgba(255,255,255,0.18);
                }}
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.ctype)


class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Dilates Crosshair Overlay')
        self.setFixedSize(920, 660)

        icon_path = os.path.join(os.path.dirname(__file__), 'crosshair.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            QApplication.setWindowIcon(QIcon(icon_path))

        config_dir = os.path.join(os.path.expanduser('~'), '.config', 'dilates-crosshair')
        self.custom_dir = os.path.join(config_dir, 'saved_custom_crosshairs')
        os.makedirs(self.custom_dir, exist_ok=True)

        self.selected_builtin = 'cross'
        self.custom_pixmaps = {} 
        self.choice_cards = {} 

        self.size_val = 14
        self.gap_val = 2
        self.color_val = QColor(0, 255, 100)
        self.rotation_val = 0
        self.opacity_val = 100
        self.outline_val = False
        self.outline_thickness_val = 1
        
        self.animation_mode = 'none' 
        self.animation_speed_val = 10
        
        self.global_anim_mode = 0  
        self.global_anim_duration = 220  
        self.global_anim_delay = 0       
        self.global_easing_curve = QEasingCurve.OutBounce  

        self.overlay_active = False
        self.overlay = None

        self.ui_bg_color = "#12141c"
        self.ui_sidebar_color = "#181b25"
        self.ui_accent_color = "#6366f1"
        self.ui_text_color = "#e5e7eb"

        # Extended UI customisation
        self.ui_card_radius = 12          # px, 0-24
        self.ui_font_size = 13            # px, 11-18
        self.ui_sidebar_opacity = 100     # %, 40-100
        self.ui_compact_mode = False      # compact sidebar
        self.ui_bg_blur = False           # glass-morphism hint

        # Config file
        self.config_file = os.path.join(
            os.path.expanduser('~'), '.config', 'dilates-crosshair', 'settings.json'
        )

        self.load_saved_customs()
        self.load_settings()
        self.initUI()

    def load_saved_customs(self):
        if not os.path.exists(self.custom_dir):
            return
        for file_name in os.listdir(self.custom_dir):
            if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                full_path = os.path.join(self.custom_dir, file_name)
                key = f"custom_{file_name}"
                pix = QPixmap(full_path)
                if not pix.isNull():
                    self.custom_pixmaps[key] = pix

    def load_settings(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                self.size_val            = d.get('size',            self.size_val)
                self.gap_val             = d.get('gap',             self.gap_val)
                self.color_val           = QColor(d.get('color',    self.color_val.name()))
                self.rotation_val        = d.get('rotation',        self.rotation_val)
                self.opacity_val         = d.get('opacity',         self.opacity_val)
                self.outline_val         = d.get('outline',         self.outline_val)
                self.outline_thickness_val = d.get('outline_thickness', self.outline_thickness_val)
                self.animation_mode      = d.get('animation_mode',  self.animation_mode)
                self.animation_speed_val = d.get('animation_speed', self.animation_speed_val)
                self.selected_builtin    = d.get('selected_builtin',self.selected_builtin)
                self.ui_bg_color         = d.get('ui_bg',           self.ui_bg_color)
                self.ui_sidebar_color    = d.get('ui_sidebar',      self.ui_sidebar_color)
                self.ui_accent_color     = d.get('ui_accent',       self.ui_accent_color)
                self.ui_text_color       = d.get('ui_text',         self.ui_text_color)
                self.ui_card_radius      = d.get('ui_card_radius',  self.ui_card_radius)
                self.ui_font_size        = d.get('ui_font_size',    self.ui_font_size)
                self.ui_sidebar_opacity  = d.get('ui_sidebar_opacity', self.ui_sidebar_opacity)
                self.ui_compact_mode     = d.get('ui_compact_mode', self.ui_compact_mode)
                self.global_anim_mode    = d.get('global_anim_mode',self.global_anim_mode)
                self.global_anim_duration= d.get('global_anim_duration', self.global_anim_duration)
                self.global_anim_delay   = d.get('global_anim_delay', self.global_anim_delay)
        except Exception:
            pass

    def save_settings(self):
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            d = {
                'size': self.size_val, 'gap': self.gap_val,
                'color': self.color_val.name(), 'rotation': self.rotation_val,
                'opacity': self.opacity_val, 'outline': self.outline_val,
                'outline_thickness': self.outline_thickness_val,
                'animation_mode': self.animation_mode,
                'animation_speed': self.animation_speed_val,
                'selected_builtin': self.selected_builtin,
                'ui_bg': self.ui_bg_color, 'ui_sidebar': self.ui_sidebar_color,
                'ui_accent': self.ui_accent_color, 'ui_text': self.ui_text_color,
                'ui_card_radius': self.ui_card_radius,
                'ui_font_size': self.ui_font_size,
                'ui_sidebar_opacity': self.ui_sidebar_opacity,
                'ui_compact_mode': self.ui_compact_mode,
                'global_anim_mode': self.global_anim_mode,
                'global_anim_duration': self.global_anim_duration,
                'global_anim_delay': self.global_anim_delay,
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(d, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def apply_stylesheet(self):
        acc = self.ui_accent_color
        bg = self.ui_bg_color
        sidebar = self.ui_sidebar_color
        text = self.ui_text_color
        r = self.ui_card_radius
        fs = self.ui_font_size
        # sidebar with configurable opacity
        so = max(40, min(100, self.ui_sidebar_opacity)) / 100.0
        sr, sg, sb = QColor(sidebar).red(), QColor(sidebar).green(), QColor(sidebar).blue()
        sidebar_rgba = f"rgba({sr},{sg},{sb},{so:.2f})"
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {bg};
                color: {text};
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: {fs}px;
            }}
            QFrame#Sidebar {{
                background-color: {sidebar_rgba};
                border-right: 1px solid rgba(255,255,255,0.05);
            }}
            QFrame#Card {{
                background-color: {sidebar};
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: {r}px;
            }}
            QFrame#PreviewCard {{
                background-color: #0a0c12;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: {r}px;
            }}
            QFrame#SidebarPreviewBox {{
                background-color: rgba(0,0,0,0.35);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: {max(6,r-2)}px;
            }}
            QPushButton#SidebarBtn {{
                background-color: transparent;
                border: none;
                border-radius: 8px;
                padding: 9px 12px;
                color: rgba(255,255,255,0.55);
                text-align: left;
                font-weight: 500;
                font-size: 13px;
            }}
            QPushButton#SidebarBtn:hover {{
                background-color: rgba(255,255,255,0.06);
                color: {text};
            }}
            QPushButton#SidebarBtn:checked {{
                background-color: {acc}22;
                color: {acc};
                font-weight: 600;
            }}
            QPushButton#ActionBtn {{
                background-color: {acc};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 9px 18px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton#ActionBtn:hover {{
                background-color: {acc}cc;
            }}
            QPushButton#ActionBtn:pressed {{
                background-color: {acc}99;
            }}
            QPushButton#GhostBtn {{
                background-color: transparent;
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 8px;
                padding: 9px 18px;
                color: {text};
                font-weight: 500;
            }}
            QPushButton#GhostBtn:hover {{
                border-color: {acc};
                color: {acc};
            }}
            QComboBox {{
                background-color: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                padding: 7px 12px;
                color: {text};
                min-height: 32px;
            }}
            QComboBox:hover {{
                border-color: {acc}88;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {sidebar};
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                selection-background-color: {acc}33;
                color: {text};
                padding: 4px;
            }}
            QLineEdit, QTextEdit {{
                background-color: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                padding: 7px 12px;
                color: {text};
            }}
            QTextEdit {{
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 12px;
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,0.12);
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(255,255,255,0.2);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QSlider::groove:horizontal {{
                border: none;
                height: 4px;
                background: rgba(255,255,255,0.08);
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {self.ui_accent_color};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: #ffffff;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
                border: 2px solid {self.ui_accent_color};
            }}
            QSlider::handle:horizontal:hover {{
                background: {self.ui_accent_color};
                border-color: #ffffff;
            }}
            QLabel#SectionHeader {{
                color: rgba(255,255,255,0.3);
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1px;
                padding: 8px 0 4px 0;
            }}
            QLabel#ValueLabel {{
                color: {self.ui_accent_color};
                font-size: 12px;
                font-weight: 600;
                min-width: 36px;
            }}
        """)
        
        for ctype, card in self.choice_cards.items():
            card.update_style()
            
        if hasattr(self, 'outline_toggle'):
            self.outline_toggle.update()

        if hasattr(self, 'logo_dot'):
            self.logo_dot.setStyleSheet(f"color: {self.ui_accent_color}; font-size: 18px;")

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(230)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 20)
        sidebar_layout.setSpacing(2)

        # Logo area
        logo_widget = QWidget()
        logo_layout = QHBoxLayout(logo_widget)
        logo_layout.setContentsMargins(4, 0, 0, 0)
        logo_layout.setSpacing(8)
        self.logo_dot = QLabel("●")
        logo_dot = self.logo_dot
        logo_dot.setStyleSheet(f"color: {self.ui_accent_color}; font-size: 18px;")
        logo_layout.addWidget(logo_dot)
        logo_label = QLabel("Dilates Cross")
        logo_label.setStyleSheet("font-size: 15px; font-weight: 700; letter-spacing: -0.3px;")
        logo_layout.addWidget(logo_label)
        logo_layout.addStretch()
        sidebar_layout.addWidget(logo_widget)
        sidebar_layout.addSpacing(16)

        # Live preview in sidebar
        self.sidebar_preview_frame = QFrame()
        self.sidebar_preview_frame.setObjectName("SidebarPreviewBox")
        self.sidebar_preview_frame.setFixedHeight(80)
        sp_layout = QVBoxLayout(self.sidebar_preview_frame)
        sp_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_preview_label = QLabel()
        self.sidebar_preview_label.setAlignment(Qt.AlignCenter)
        sp_layout.addWidget(self.sidebar_preview_label)
        sidebar_layout.addWidget(self.sidebar_preview_frame)
        sidebar_layout.addSpacing(12)

        # Nav section header
        nav_header = QLabel("НАВИГАЦИЯ")
        nav_header.setObjectName("SectionHeader")
        sidebar_layout.addWidget(nav_header)

        self.btn_tab_main = self.create_nav_btn("🎯  Прицелы", 0, True)
        self.btn_tab_code = self.create_nav_btn("🌐  Сайты с PNG", 1, False)
        self.btn_tab_custom = self.create_nav_btn("🖼️  Загрузить PNG", 2, False)
        self.btn_tab_settings = self.create_nav_btn("⚙️  Настройки", 3, False)
        self.btn_tab_ui = self.create_nav_btn("🎨  Интерфейс", 4, False)
        self.btn_tab_export = self.create_nav_btn("🛠️  Экспорт/Импорт", 5, False)
        self.btn_tab_about = self.create_nav_btn("ℹ️  О программе", 6, False)

        for btn in [self.btn_tab_main, self.btn_tab_code, self.btn_tab_custom,
                    self.btn_tab_settings, self.btn_tab_ui, self.btn_tab_export, self.btn_tab_about]:
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        # Overlay toggle button — big and prominent
        self.toggle_btn = QPushButton("⬤  OVERLAY ВЫКЛ")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setMinimumHeight(44)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239,68,68,0.15);
                color: #ef4444;
                border: 1px solid rgba(239,68,68,0.35);
                font-weight: 700;
                font-size: 13px;
                text-align: center;
                padding: 10px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: rgba(239,68,68,0.25);
            }
            QPushButton:checked {
                background-color: rgba(34,197,94,0.15);
                color: #22c55e;
                border: 1px solid rgba(34,197,94,0.35);
            }
            QPushButton:checked:hover {
                background-color: rgba(34,197,94,0.25);
            }
        """)
        self.toggle_btn.clicked.connect(self.toggle_overlay)
        sidebar_layout.addWidget(self.toggle_btn)

        main_layout.addWidget(self.sidebar)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("background: transparent;")
        
        self.pages = [
            self.create_crosshairs_page(),
            self.create_code_page(),
            self.create_custom_page(),
            self.create_settings_page(),
            self.create_ui_settings_page(),
            self.create_export_page(),
            self.create_about_page()
        ]

        for p in self.pages:
            self.stacked_widget.addWidget(p)

        wrapper_widget = QWidget()
        wrapper_layout = QVBoxLayout(wrapper_widget)
        wrapper_layout.setContentsMargins(20, 20, 20, 20)
        wrapper_layout.addWidget(self.stacked_widget)

        main_layout.addWidget(wrapper_widget)
        
        self.apply_stylesheet()
        self.update_preview()
        
        self.switch_tab(0)

    def create_nav_btn(self, text, index, checked):
        btn = QPushButton(text)
        btn.setObjectName("SidebarBtn")
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.clicked.connect(lambda: self.switch_tab(index))
        return btn

    def switch_tab(self, index):
        self.stacked_widget.setCurrentIndex(index)
        
        nav_btns = [
            self.btn_tab_main, self.btn_tab_code, self.btn_tab_custom, 
            self.btn_tab_settings, self.btn_tab_ui, self.btn_tab_export, self.btn_tab_about
        ]
        for i, btn in enumerate(nav_btns):
            btn.setChecked(i == index)
            
        current_page = self.pages[index]
        current_page.setGraphicsEffect(None)
        current_page.move(0, 0)
        
        if self.global_anim_mode == 3:
            return

        delay = self.global_anim_delay
        if delay > 0:
            QTimer.singleShot(delay, lambda: self.start_page_animation(current_page))
        else:
            self.start_page_animation(current_page)

    def start_page_animation(self, current_page):
        dur = self.global_anim_duration
        curve = self.global_easing_curve

        if self.global_anim_mode == 0: # Плавный отскок (Bounce)
            self.fade_effect = QGraphicsOpacityEffect(current_page)
            current_page.setGraphicsEffect(self.fade_effect)
            
            self.anim_opacity = QPropertyAnimation(self.fade_effect, b"opacity", self)
            self.anim_opacity.setDuration(dur)
            self.anim_opacity.setStartValue(0.0)
            self.anim_opacity.setEndValue(1.0)
            
            self.anim_pos = QPropertyAnimation(current_page, b"pos", self)
            self.anim_pos.setDuration(dur)
            self.anim_pos.setStartValue(QPoint(0, 30))
            self.anim_pos.setEndValue(QPoint(0, 0))
            self.anim_pos.setEasingCurve(curve)
            
            self.anim_opacity.start()
            self.anim_pos.start()

        elif self.global_anim_mode == 1: # Плавное затухание (Fade In)
            self.fade_effect = QGraphicsOpacityEffect(current_page)
            current_page.setGraphicsEffect(self.fade_effect)
            
            self.page_anim = QPropertyAnimation(self.fade_effect, b"opacity", self)
            self.page_anim.setDuration(dur)
            self.page_anim.setStartValue(0.0)
            self.page_anim.setEndValue(1.0)
            self.page_anim.setEasingCurve(curve)
            self.page_anim.start()

        elif self.global_anim_mode == 2: # Плавный скок снизу (Slide Up)
            self.fade_effect = QGraphicsOpacityEffect(current_page)
            current_page.setGraphicsEffect(self.fade_effect)
            
            self.anim_opacity = QPropertyAnimation(self.fade_effect, b"opacity", self)
            self.anim_opacity.setDuration(dur)
            self.anim_opacity.setStartValue(0.0)
            self.anim_opacity.setEndValue(1.0)
            
            self.anim_pos = QPropertyAnimation(current_page, b"pos", self)
            self.anim_pos.setDuration(dur)
            self.anim_pos.setStartValue(QPoint(0, 45))
            self.anim_pos.setEndValue(QPoint(0, 0))
            self.anim_pos.setEasingCurve(curve)
            
            self.anim_opacity.start()
            self.anim_pos.start()

    def generate_crosshair_preview_pixmap(self, ctype):
        W, H = 120, 50
        canvas = QPixmap(W, H)
        canvas.fill(Qt.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Custom PNG: draw the actual image centred
        if ctype.startswith('custom_'):
            src = self.custom_pixmaps.get(ctype)
            if src and not src.isNull():
                scaled = src.scaled(W - 8, H - 8, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                painter.drawPixmap((W - scaled.width()) // 2, (H - scaled.height()) // 2, scaled)
            painter.end()
            return canvas

        cx, cy = W // 2, H // 2
        size = 14
        color = QColor(self.ui_text_color)
        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)

        if ctype == 'cross':
            painter.setBrush(color)
            painter.drawLine(cx - size, cy, cx + size, cy)
            painter.drawLine(cx, cy - size, cx, cy + size)
        elif ctype == 'dot':
            painter.setBrush(color)
            painter.drawEllipse(cx - 4, cy - 4, 8, 8)
        elif ctype == 'circle':
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(cx - size, cy - size, size * 2, size * 2)
        elif ctype == 'cross_circle':
            painter.setBrush(color)
            painter.drawLine(cx - size, cy, cx + size, cy)
            painter.drawLine(cx, cy - size, cx, cy + size)
            painter.setBrush(Qt.NoBrush)
            r = size // 2
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        elif ctype == 'T-shape':
            painter.setBrush(color)
            painter.drawLine(cx - size, cy, cx + size, cy)
            painter.drawLine(cx, cy - size, cx, cy)
        elif ctype == 'arrow':
            pts_x = [cx, cx + size, cx + size//2, cx + size, cx, cx - size + size//2, cx - size]
            painter.setBrush(color)
            painter.drawLine(cx - size, cy, cx + size, cy)
            painter.drawLine(cx, cy - size, cx, cy)
            painter.drawLine(cx - size//2, cy - size//2, cx, cy - size)
            painter.drawLine(cx + size//2, cy - size//2, cx, cy - size)
        elif ctype == 'square':
            painter.setBrush(Qt.NoBrush)
            s = size - 2
            painter.drawRect(cx - s, cy - s, s * 2, s * 2)
        elif ctype == 'diamond':
            painter.setBrush(Qt.NoBrush)
            painter.translate(cx, cy)
            painter.rotate(45)
            s = size - 2
            painter.drawRect(-s, -s, s * 2, s * 2)

        painter.end()
        return canvas

    def create_crosshairs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Header
        header = QLabel("Выберите прицел")
        header.setStyleSheet("font-size: 18px; font-weight: 700; letter-spacing: -0.3px;")
        layout.addWidget(header)
        sub = QLabel("Нажмите на карточку чтобы применить прицел")
        sub.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.35); margin-top: -6px;")
        layout.addWidget(sub)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        grid = QGridLayout(container)
        grid.setSpacing(10)
        grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.choice_cards.clear()

        builtins = [
            ('cross',       'Крест'),
            ('dot',         'Точка'),
            ('circle',      'Круг'),
            ('cross_circle','Кольцо'),
            ('T-shape',     'Т-образный'),
            ('square',      'Квадрат'),
            ('diamond',     'Ромб'),
        ]

        COLS = 3
        row, col = 0, 0
        for ctype, name in builtins:
            pix = self.generate_crosshair_preview_pixmap(ctype)
            card = CrosshairCard(ctype, name, pix, self)
            card.setChecked(ctype == self.selected_builtin)
            card.clicked.connect(self.select_builtin)
            grid.addWidget(card, row, col)
            self.choice_cards[ctype] = card
            col += 1
            if col >= COLS:
                col = 0
                row += 1

        for key, pixmap in self.custom_pixmaps.items():
            display_name = key.replace("custom_", "")
            if len(display_name) > 16:
                display_name = display_name[:13] + "..."
            card = CrosshairCard(key, display_name, pixmap, self)
            card.setChecked(key == self.selected_builtin)
            card.clicked.connect(self.select_builtin)
            grid.addWidget(card, row, col)
            self.choice_cards[key] = card
            col += 1
            if col >= COLS:
                col = 0
                row += 1

        grid.setRowStretch(row + 1, 1)
        for c in range(COLS):
            grid.setColumnStretch(c, 0)
        grid.setColumnStretch(COLS, 1)

        scroll.setWidget(container)
        layout.addWidget(scroll)
        return page

    def create_code_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header = QLabel("Сайты с PNG прицелами")
        header.setStyleSheet("font-size: 18px; font-weight: 700; letter-spacing: -0.3px;")
        layout.addWidget(header)
        sub = QLabel("Скачайте PNG с прозрачным фоном, затем загрузите во вкладке «Загрузить PNG»")
        sub.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.35); margin-top: -6px;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(10)

        sites = [
            ("Icons8 — Прицелы", "https://icons8.ru/icons/set/%D0%BF%D1%80%D0%B8%D1%86%D0%B5%D0%BB"),
            ("Flaticon — Crosshair icons", "https://www.flaticon.com/free-icons/crosshair"),
        ]
        for site_name, url in sites:
            btn = QPushButton(f"🌐  {site_name}")
            btn.setObjectName("ActionBtn")
            btn.setMinimumHeight(44)
            btn.clicked.connect(lambda checked, u=url: QDesktopServices.openUrl(QUrl(u)))
            cl.addWidget(btn)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def refresh_crosshairs_grid(self):
        old_page = self.pages[0]
        new_page = self.create_crosshairs_page()
        
        self.stacked_widget.removeWidget(old_page)
        self.pages[0] = new_page
        self.stacked_widget.insertWidget(0, new_page)
        
        if self.stacked_widget.currentIndex() == 0:
            self.switch_tab(0)
        old_page.deleteLater()

    def select_builtin(self, ctype):
        self.selected_builtin = ctype
        for t, card in self.choice_cards.items():
            card.setChecked(t == ctype)
        self.on_setting_changed()

    def create_custom_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header = QLabel("Загрузить PNG")
        header.setStyleSheet("font-size: 18px; font-weight: 700; letter-spacing: -0.3px;")
        layout.addWidget(header)
        sub = QLabel("Используйте собственное изображение прицела")
        sub.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.35); margin-top: -6px;")
        layout.addWidget(sub)

        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 16, 18, 20)
        cl.setSpacing(14)

        tip = QLabel(
            "Рекомендуется использовать PNG с прозрачным фоном.\n"
            "После загрузки прицел появится в разделе «Прицелы» и будет выбран автоматически."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 12px; line-height: 1.5;")
        cl.addWidget(tip)

        btn_load = QPushButton("📁  Выбрать PNG файл")
        btn_load.setObjectName("ActionBtn")
        btn_load.setMinimumHeight(44)
        btn_load.clicked.connect(self.load_custom_png)
        cl.addWidget(btn_load)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def load_custom_png(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать PNG прицел", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            file_name = os.path.basename(path)
            dest_path = os.path.join(self.custom_dir, file_name)
            
            if not os.path.exists(dest_path) or os.path.abspath(path) != os.path.abspath(dest_path):
                shutil.copy(path, dest_path)
            
            pix = QPixmap(dest_path)
            if not pix.isNull():
                key = f"custom_{file_name}"
                self.custom_pixmaps[key] = pix
                self.selected_builtin = key
                
                self.refresh_crosshairs_grid()
                self.on_setting_changed()
                self.switch_tab(0)

    def _make_slider_row(self, label_text, slider_widget, suffix=""):
        """Helper: returns a layout with label, slider, and live value label."""
        container = QWidget()
        vl = QVBoxLayout(container)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(4)

        top_row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 12px;")
        top_row.addWidget(lbl)
        top_row.addStretch()
        val_lbl = QLabel(str(slider_widget.value()) + suffix)
        val_lbl.setObjectName("ValueLabel")
        top_row.addWidget(val_lbl)
        vl.addLayout(top_row)
        vl.addWidget(slider_widget)

        def on_change(v):
            val_lbl.setText(str(v) + suffix)
        slider_widget.valueChanged.connect(on_change)
        return container

    def create_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header = QLabel("Настройки прицела")
        header.setStyleSheet("font-size: 18px; font-weight: 700; letter-spacing: -0.3px;")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 8, 0)
        cl.setSpacing(10)

        # --- Preview box (prominent) ---
        preview_frame = QFrame()
        preview_frame.setObjectName("PreviewCard")
        preview_frame.setFixedHeight(90)
        pf_layout = QVBoxLayout(preview_frame)
        pf_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_box = QLabel()
        self.preview_box.setAlignment(Qt.AlignCenter)
        pf_layout.addWidget(self.preview_box)
        cl.addWidget(preview_frame)

        # --- Appearance card ---
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)

        sec1 = QLabel("ВНЕШНИЙ ВИД")
        sec1.setObjectName("SectionHeader")
        card_layout.addWidget(sec1)

        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(4, 50)
        self.size_slider.setValue(self.size_val)
        self.size_slider.valueChanged.connect(self.on_setting_changed)
        card_layout.addWidget(self._make_slider_row("Размер", self.size_slider, " px"))

        self.gap_slider = QSlider(Qt.Horizontal)
        self.gap_slider.setRange(0, 20)
        self.gap_slider.setValue(self.gap_val)
        self.gap_slider.valueChanged.connect(self.on_setting_changed)
        card_layout.addWidget(self._make_slider_row("Центральный зазор", self.gap_slider, " px"))

        self.rot_slider = QSlider(Qt.Horizontal)
        self.rot_slider.setRange(0, 360)
        self.rot_slider.setValue(self.rotation_val)
        self.rot_slider.valueChanged.connect(self.on_setting_changed)
        card_layout.addWidget(self._make_slider_row("Вращение", self.rot_slider, "°"))

        self.op_slider = QSlider(Qt.Horizontal)
        self.op_slider.setRange(10, 100)
        self.op_slider.setValue(self.opacity_val)
        self.op_slider.valueChanged.connect(self.on_setting_changed)
        card_layout.addWidget(self._make_slider_row("Прозрачность", self.op_slider, "%"))

        # Color button
        color_row = QHBoxLayout()
        color_lbl = QLabel("Цвет прицела")
        color_lbl.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 12px;")
        color_row.addWidget(color_lbl)
        color_row.addStretch()
        self.color_btn = QPushButton("  ●  Выбрать")
        self.color_btn.setFixedHeight(34)
        self.color_btn.setMinimumWidth(120)
        self.update_color_btn_style()
        self.color_btn.clicked.connect(self.open_color_dialog)
        color_row.addWidget(self.color_btn)
        card_layout.addLayout(color_row)

        # Outline row
        outline_row = QHBoxLayout()
        outline_lbl = QLabel("Обводка (Outline)")
        outline_lbl.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 12px;")
        outline_row.addWidget(outline_lbl)
        outline_row.addStretch()
        self.outline_toggle = AnimatedToggle()
        self.outline_toggle.setChecked(self.outline_val)
        self.outline_toggle.clicked.connect(self.on_setting_changed)
        outline_row.addWidget(self.outline_toggle)
        card_layout.addLayout(outline_row)

        self.outline_thick_slider = QSlider(Qt.Horizontal)
        self.outline_thick_slider.setRange(1, 5)
        self.outline_thick_slider.setValue(self.outline_thickness_val)
        self.outline_thick_slider.valueChanged.connect(self.on_setting_changed)
        card_layout.addWidget(self._make_slider_row("Толщина обводки", self.outline_thick_slider))

        cl.addWidget(card)

        # --- Animation card ---
        anim_card = QFrame()
        anim_card.setObjectName("Card")
        anim_card_layout = QVBoxLayout(anim_card)
        anim_card_layout.setContentsMargins(18, 16, 18, 16)
        anim_card_layout.setSpacing(12)

        sec2 = QLabel("АНИМАЦИЯ ПРИЦЕЛА")
        sec2.setObjectName("SectionHeader")
        anim_card_layout.addWidget(sec2)

        anim_lbl = QLabel("Режим анимации")
        anim_lbl.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 12px;")
        anim_card_layout.addWidget(anim_lbl)
        self.anim_combo = QComboBox()
        self.anim_combo.addItems([
            "Без анимации",
            "Пульсация",
            "Вращение",
            "Дыхание",
            "Волна (Gap)"
        ])
        self.anim_combo.currentIndexChanged.connect(self.on_animation_changed)
        anim_card_layout.addWidget(self.anim_combo)

        self.anim_speed_slider = QSlider(Qt.Horizontal)
        self.anim_speed_slider.setRange(2, 30)
        self.anim_speed_slider.setValue(self.animation_speed_val)
        self.anim_speed_slider.valueChanged.connect(self.on_setting_changed)
        anim_card_layout.addWidget(self._make_slider_row("Скорость", self.anim_speed_slider))

        cl.addWidget(anim_card)
        cl.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

        return page

    def create_ui_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(15)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(24) 

        # --- ГРУППА 1: НАСТРОЙКИ ИНТЕРФЕЙСА ---
        ui_card = QFrame()
        ui_card.setObjectName("Card")
        ui_card_layout = QVBoxLayout(ui_card)
        ui_card_layout.setContentsMargins(15, 15, 15, 15)
        ui_card_layout.setSpacing(12)

        ui_card_layout.addWidget(QLabel("<b>🎨 Настройки интерфейса</b>", styleSheet="font-size: 14px; color: #a5b4fc; margin-bottom: 4px;"))

        ui_form = QFormLayout()
        ui_form.setSpacing(12)
        ui_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.theme_combo = QComboBox()
        themes = [
            "Темная классическая (Cyber)",
            "Темный углерод (Dark Carbon)",
            "Светлая минималистичная",
            "Неоновая фиолетовая",
            "Кровавая луна (Red)",
            "Хакерская (Matrix)",
            "Океанская бездна (Blue)"
        ]
        self.theme_combo.addItems(themes)
        self.theme_combo.setMinimumHeight(32)
        self.theme_combo.currentIndexChanged.connect(self.change_ui_theme)
        ui_form.addRow("Готовые цветовые темы:", self.theme_combo)

        self.ui_accent_btn = QPushButton("ВЫБРАТЬ ЦВЕТ")
        self.ui_accent_btn.setObjectName("ActionBtn")
        self.ui_accent_btn.setMinimumHeight(32)
        self.ui_accent_btn.clicked.connect(self.open_ui_accent_dialog)
        ui_form.addRow("Акцентный цвет интерфейса:", self.ui_accent_btn)

        ui_card_layout.addLayout(ui_form)
        scroll_layout.addWidget(ui_card)

        # --- ГРУППА 2: НАСТРОЙКИ АНИМАЦИИ ---
        anim_card = QFrame()
        anim_card.setObjectName("Card")
        anim_card_layout = QVBoxLayout(anim_card)
        anim_card_layout.setContentsMargins(15, 15, 15, 15)
        anim_card_layout.setSpacing(12)

        anim_card_layout.addWidget(QLabel("<b>✨ Настройки анимации</b>", styleSheet="font-size: 14px; color: #a5b4fc; margin-bottom: 4px;"))

        anim_form = QFormLayout()
        anim_form.setSpacing(12)
        anim_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.global_anim_combo = QComboBox()
        global_animations = [
            "1. Плавный отскок (Bounce)",
            "2. Плавное затухание (Fade)",
            "3. Плавный скок снизу (Slide Up)",
            "4. Отключить анимации полностью"
        ]
        self.global_anim_combo.addItems(global_animations)
        self.global_anim_combo.setCurrentIndex(self.global_anim_mode)
        self.global_anim_combo.setMinimumHeight(32)
        self.global_anim_combo.currentIndexChanged.connect(self.change_global_animation_mode)
        anim_form.addRow("Переключатель анимаций интерфейса:", self.global_anim_combo)

        self.anim_duration_slider = QSlider(Qt.Horizontal)
        self.anim_duration_slider.setRange(50, 800)
        self.anim_duration_slider.setValue(self.global_anim_duration)
        self.anim_duration_slider.setSingleStep(10)
        self.anim_duration_slider.valueChanged.connect(self.change_global_animation_duration)
        self.anim_duration_label = QLabel(f"{self.global_anim_duration} мс")
        self.anim_duration_label.setStyleSheet("font-weight: bold; color: #a5b4fc;")
        
        dur_row = QHBoxLayout()
        dur_row.addWidget(self.anim_duration_slider)
        dur_row.addWidget(self.anim_duration_label)
        anim_form.addRow("Длительность переходов:", dur_row)

        self.anim_delay_slider = QSlider(Qt.Horizontal)
        self.anim_delay_slider.setRange(0, 300)
        self.anim_delay_slider.setValue(self.global_anim_delay)
        self.anim_delay_slider.setSingleStep(10)
        self.anim_delay_slider.valueChanged.connect(self.change_global_animation_delay)
        self.anim_delay_label = QLabel(f"{self.global_anim_delay} мс")
        self.anim_delay_label.setStyleSheet("font-weight: bold; color: #a5b4fc;")
        
        delay_row = QHBoxLayout()
        delay_row.addWidget(self.anim_delay_slider)
        delay_row.addWidget(self.anim_delay_label)
        anim_form.addRow("Задержка перед анимацией (Delay):", delay_row)

        anim_card_layout.addLayout(anim_form)
        scroll_layout.addWidget(anim_card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        return page

    def create_export_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header = QLabel("Экспорт / Импорт")
        header.setStyleSheet("font-size: 18px; font-weight: 700; letter-spacing: -0.3px;")
        layout.addWidget(header)
        sub = QLabel("Конфигурация прицела в формате JSON")
        sub.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.35); margin-top: -6px;")
        layout.addWidget(sub)

        self.config_text_area = QTextEdit()
        self.config_text_area.setMinimumHeight(160)
        self.update_config_json_view()
        layout.addWidget(self.config_text_area)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_copy = QPushButton("📋  Скопировать")
        btn_copy.setObjectName("ActionBtn")
        btn_copy.setMinimumHeight(40)
        btn_copy.clicked.connect(self.copy_config_to_clipboard)
        
        btn_apply = QPushButton("📥  Применить")
        btn_apply.setObjectName("GhostBtn")
        btn_apply.setMinimumHeight(40)
        btn_apply.clicked.connect(self.apply_config_from_text)
        
        btn_row.addWidget(btn_copy)
        btn_row.addWidget(btn_apply)
        layout.addLayout(btn_row)

        return page

    def update_config_json_view(self):
        config_data = {
            "selected_builtin": self.selected_builtin,
            "size": self.size_val,
            "gap": self.gap_val,
            "color": self.color_val.name(),
            "rotation": self.rotation_val,
            "opacity": self.opacity_val,
            "outline": self.outline_val,
            "outline_thickness": self.outline_thickness_val,
            "animation_mode": self.animation_mode,
            "animation_speed": self.animation_speed_val
        }
        if hasattr(self, 'config_text_area'):
            self.config_text_area.setText(json.dumps(config_data, indent=4, ensure_ascii=False))

    def copy_config_to_clipboard(self):
        self.update_config_json_view()
        clipboard = QApplication.clipboard()
        clipboard.setText(self.config_text_area.toPlainText())

    def apply_config_from_text(self):
        try:
            data = json.loads(self.config_text_area.toPlainText())
            if "size" in data: self.size_val = data["size"]
            if "gap" in data: self.gap_val = data["gap"]
            if "color" in data: self.color_val = QColor(data["color"])
            if "rotation" in data: self.rotation_val = data["rotation"]
            if "opacity" in data: self.opacity_val = data["opacity"]
            if "outline" in data: self.outline_val = data["outline"]
            if "outline_thickness" in data: self.outline_thickness_val = data["outline_thickness"]
            if "animation_mode" in data: self.animation_mode = data["animation_mode"]
            if "animation_speed" in data: self.animation_speed_val = data["animation_speed"]
            if "selected_builtin" in data: self.selected_builtin = data["selected_builtin"]

            if hasattr(self, 'size_slider'): self.size_slider.setValue(self.size_val)
            if hasattr(self, 'gap_slider'): self.gap_slider.setValue(self.gap_val)
            if hasattr(self, 'rot_slider'): self.rot_slider.setValue(self.rotation_val)
            if hasattr(self, 'op_slider'): self.op_slider.setValue(self.opacity_val)
            if hasattr(self, 'anim_speed_slider'): self.anim_speed_slider.setValue(self.animation_speed_val)
            if hasattr(self, 'outline_toggle'): self.outline_toggle.setChecked(self.outline_val)
            if hasattr(self, 'outline_thick_slider'): self.outline_thick_slider.setValue(self.outline_thickness_val)
            self.update_color_btn_style()
            self.update_preview()
        except Exception:
            pass

    def create_about_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header = QLabel("О программе")
        header.setStyleSheet("font-size: 18px; font-weight: 700; letter-spacing: -0.3px;")
        layout.addWidget(header)

        info_card = QFrame()
        info_card.setObjectName("Card")
        info_card_layout = QVBoxLayout(info_card)
        info_card_layout.setContentsMargins(20, 20, 20, 20)
        info_card_layout.setSpacing(14)

        app_name = QLabel("Dilates Crosshair")
        app_name.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {self.ui_accent_color}; letter-spacing: -0.5px;")
        info_card_layout.addWidget(app_name)

        version = QLabel("Версия 2.6.0  ·  Linux · X11 · Wayland")
        version.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.35);")
        info_card_layout.addWidget(version)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: rgba(255,255,255,0.07);")
        info_card_layout.addWidget(divider)

        for label, value in [
            ("Описание", "Профессиональный оверлей прицела с поддержкой PNG текстур, анимаций и полной кастомизации."),
            ("Управление оверлеем", "Кнопка «OVERLAY ВКЛ/ВЫКЛ» в левой панели."),
        ]:
            row_w = QWidget()
            row_l = QVBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(2)
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: rgba(255,255,255,0.35); letter-spacing: 0.5px;")
            row_l.addWidget(lbl)
            val = QLabel(value)
            val.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.75);")
            val.setWordWrap(True)
            row_l.addWidget(val)
            info_card_layout.addWidget(row_w)

        repo_btn = QPushButton("🌐  Открыть репозиторий")
        repo_btn.setObjectName("ActionBtn")
        repo_btn.setMinimumHeight(42)
        repo_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com")))
        info_card_layout.addWidget(repo_btn)

        layout.addWidget(info_card)
        layout.addStretch()
        return page

    def change_global_animation_mode(self, index):
        self.global_anim_mode = index
        
        # 4 оставшихся режима (масштабирование и линейный удалены)
        curves = [
            QEasingCurve.OutBounce, # 1. Плавный отскок
            QEasingCurve.InOutQuad, # 2. Плавное затухание
            QEasingCurve.OutCubic,  # 3. Плавный скок снизу
            QEasingCurve.Linear     # 4. Отключено
        ]
        if 0 <= index < len(curves):
            self.global_easing_curve = curves[index]

        is_enabled = index != 3
        if hasattr(self, 'anim_duration_slider'):
            self.anim_duration_slider.setEnabled(is_enabled)
        if hasattr(self, 'anim_delay_slider'):
            self.anim_delay_slider.setEnabled(is_enabled)

    def change_global_animation_duration(self, value):
        self.global_anim_duration = value
        if hasattr(self, 'anim_duration_label'):
            self.anim_duration_label.setText(f"{value} мс")

    def change_global_animation_delay(self, value):
        self.global_anim_delay = value
        if hasattr(self, 'anim_delay_label'):
            self.anim_delay_label.setText(f"{value} мс")

    def change_ui_theme(self, index):
        if index == 0: 
            self.ui_bg_color = "#12141c"
            self.ui_sidebar_color = "#181b25"
            self.ui_accent_color = "#6366f1"
            self.ui_text_color = "#e5e7eb"
        elif index == 1: 
            self.ui_bg_color = "#0a0a0a"
            self.ui_sidebar_color = "#141414"
            self.ui_accent_color = "#3b82f6"
            self.ui_text_color = "#f3f4f6"
        elif index == 2: 
            self.ui_bg_color = "#f3f4f6"
            self.ui_sidebar_color = "#ffffff"
            self.ui_accent_color = "#2563eb"
            self.ui_text_color = "#1f2937"
        elif index == 3: 
            self.ui_bg_color = "#110c1d"
            self.ui_sidebar_color = "#1a122c"
            self.ui_accent_color = "#a855f7"
            self.ui_text_color = "#f3e8ff"
        elif index == 4: 
            self.ui_bg_color = "#1a0b0b"
            self.ui_sidebar_color = "#2a1212"
            self.ui_accent_color = "#ef4444"
            self.ui_text_color = "#fecaca"
        elif index == 5: 
            self.ui_bg_color = "#050505"
            self.ui_sidebar_color = "#0a0a0a"
            self.ui_accent_color = "#22c55e"
            self.ui_text_color = "#bbf7d0"
        elif index == 6: 
            self.ui_bg_color = "#0f172a"
            self.ui_sidebar_color = "#1e293b"
            self.ui_accent_color = "#0ea5e9"
            self.ui_text_color = "#e0f2fe"
            
        self.apply_stylesheet()
        self.refresh_crosshairs_grid()

    def open_ui_accent_dialog(self):
        col = QColorDialog.getColor(QColor(self.ui_accent_color), self, "Выбор акцентного цвета")
        if col.isValid():
            self.ui_accent_color = col.name()
            self.apply_stylesheet()
            self.refresh_crosshairs_grid()

    def open_color_dialog(self):
        col = QColorDialog.getColor(self.color_val, self, "Выбор цвета прицела")
        if col.isValid():
            self.color_val = col
            self.update_color_btn_style()
            self.on_setting_changed()

    def update_color_btn_style(self):
        # Determine readable text color based on luminance
        r, g, b = self.color_val.red(), self.color_val.green(), self.color_val.blue()
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        text_c = "#000000" if luminance > 140 else "#ffffff"
        self.color_btn.setStyleSheet(
            f"background-color: {self.color_val.name()}; color: {text_c}; "
            f"font-weight: 700; border-radius: 8px; padding: 0 14px; border: none;"
        )

    def toggle_overlay(self, checked):
        self.overlay_active = checked
        if checked:
            self.toggle_btn.setText("⬤  OVERLAY ВКЛ")
            if not self.overlay:
                self.overlay = CrosshairOverlay(self)
            self.overlay.show()
        else:
            self.toggle_btn.setText("⬤  OVERLAY ВЫКЛ")
            if self.overlay:
                self.overlay.hide()

    def on_animation_changed(self, index):
        modes = ['none', 'pulse', 'spin', 'breathing', 'wave', 'rainbow', 'shake', 'flicker', 'orbit']
        if 0 <= index < len(modes):
            self.animation_mode = modes[index]
        self.on_setting_changed()

    def on_setting_changed(self):
        self.size_val = self.size_slider.value() if hasattr(self, 'size_slider') else self.size_val
        self.gap_val = self.gap_slider.value() if hasattr(self, 'gap_slider') else self.gap_val
        self.rotation_val = self.rot_slider.value() if hasattr(self, 'rot_slider') else self.rotation_val
        self.opacity_val = self.op_slider.value() if hasattr(self, 'op_slider') else self.opacity_val
        self.animation_speed_val = self.anim_speed_slider.value() if hasattr(self, 'anim_speed_slider') else self.animation_speed_val
        self.outline_val = self.outline_toggle.isChecked() if hasattr(self, 'outline_toggle') else self.outline_val
        self.outline_thickness_val = self.outline_thick_slider.value() if hasattr(self, 'outline_thick_slider') else self.outline_thickness_val
        
        self.update_preview()
        self.update_config_json_view()
        if hasattr(self, 'overlay') and self.overlay:
            self.overlay.update()

    def update_sidebar_preview(self):
        if not hasattr(self, 'sidebar_preview_label'):
            return
        canvas = QPixmap(self.sidebar_preview_frame.size())
        canvas.fill(Qt.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing, True)
        opacity = self.opacity_val / 100.0
        painter.setOpacity(opacity)
        cx = canvas.width() // 2
        cy = canvas.height() // 2
        size = min(self.size_val, 18)
        gap = min(self.gap_val, size - 2)
        color = self.color_val
        rotation = self.rotation_val
        has_outline = self.outline_val
        outline_thickness = self.outline_thickness_val

        if not self.selected_builtin.startswith('custom_'):
            base_width = max(1, size // 5)
            def draw_sp(p_pen, p_brush_color):
                painter.setPen(p_pen)
                painter.resetTransform()
                painter.translate(cx, cy)
                painter.rotate(rotation)
                ctype = self.selected_builtin
                if ctype == 'cross':
                    painter.setBrush(p_brush_color)
                    if gap <= 0:
                        painter.drawLine(int(-size), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, int(size))
                    else:
                        painter.drawLine(int(-size), 0, int(-gap), 0)
                        painter.drawLine(int(gap), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, int(-gap))
                        painter.drawLine(0, int(gap), 0, int(size))
                elif ctype == 'dot':
                    painter.setBrush(p_brush_color)
                    r = max(2, int(size // 3))
                    painter.drawEllipse(-r, -r, r * 2, r * 2)
                elif ctype == 'circle':
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(int(-size), int(-size), int(size * 2), int(size * 2))
                elif ctype == 'cross_circle':
                    painter.setBrush(p_brush_color)
                    if gap <= 0:
                        painter.drawLine(int(-size), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, int(size))
                    else:
                        painter.drawLine(int(-size), 0, int(-gap), 0)
                        painter.drawLine(int(gap), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, int(-gap))
                        painter.drawLine(0, int(gap), 0, int(size))
                    painter.setBrush(Qt.NoBrush)
                    r = int(size // 2)
                    painter.drawEllipse(-r, -r, r * 2, r * 2)
                elif ctype == 'T-shape':
                    painter.setBrush(p_brush_color)
                    if gap <= 0:
                        painter.drawLine(int(-size), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, 0)
                    else:
                        painter.drawLine(int(-size), 0, int(-gap), 0)
                        painter.drawLine(int(gap), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, int(-gap))
                painter.resetTransform()

            if has_outline:
                op = QPen(QColor(0, 0, 0))
                op.setWidth(base_width + outline_thickness * 2)
                draw_sp(op, QColor(0, 0, 0))
            mp = QPen(color)
            mp.setWidth(base_width)
            draw_sp(mp, color)
        painter.end()
        self.sidebar_preview_label.setPixmap(canvas)

    def update_preview(self):
        if not hasattr(self, 'preview_box'):
            return
        self.update_sidebar_preview()
        size = self.preview_box.size()
        if size.width() < 10 or size.height() < 10:
            return
        canvas = QPixmap(size)
        canvas.fill(Qt.transparent)
        
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        opacity = self.opacity_val / 100.0
        painter.setOpacity(opacity)
        
        cx = canvas.width() // 2
        cy = canvas.height() // 2
        size = min(self.size_val, 22)
        gap = min(self.gap_val, size - 2)
        color = self.color_val
        rotation = self.rotation_val
        has_outline = self.outline_val
        outline_thickness = self.outline_thickness_val
        
        if self.selected_builtin.startswith('custom_'):
            pixmap = self.custom_pixmaps.get(self.selected_builtin)
            if pixmap and not pixmap.isNull():
                pix = pixmap.scaled(size * 3, size * 3, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                if rotation != 0:
                    painter.translate(cx, cy)
                    painter.rotate(rotation)
                    painter.drawPixmap(-pix.width() // 2, -pix.height() // 2, pix)
                else:
                    painter.drawPixmap(cx - pix.width() // 2, cy - pix.height() // 2, pix)
        else:
            base_width = max(1, size // 5)

            def draw_preview_shapes(p_pen, p_brush_color):
                painter.setPen(p_pen)
                painter.resetTransform()
                painter.translate(cx, cy)
                painter.rotate(rotation)
                
                ctype = self.selected_builtin
                if ctype == 'cross':
                    painter.setBrush(p_brush_color)
                    if gap <= 0:
                        painter.drawLine(int(-size), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, int(size))
                    else:
                        painter.drawLine(int(-size), 0, int(-gap), 0)
                        painter.drawLine(int(gap), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, int(-gap))
                        painter.drawLine(0, int(gap), 0, int(size))
                elif ctype == 'dot':
                    painter.setBrush(p_brush_color)
                    r = max(2, int(size // 3))
                    painter.drawEllipse(-r, -r, r * 2, r * 2)
                elif ctype == 'circle':
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(int(-size), int(-size), int(size * 2), int(size * 2))
                elif ctype == 'cross_circle':
                    painter.setBrush(p_brush_color)
                    if gap <= 0:
                        painter.drawLine(int(-size), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, int(size))
                    else:
                        painter.drawLine(int(-size), 0, int(-gap), 0)
                        painter.drawLine(int(gap), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, int(-gap))
                        painter.drawLine(0, int(gap), 0, int(size))
                    painter.setBrush(Qt.NoBrush)
                    r = int(size // 2)
                    painter.drawEllipse(-r, -r, r * 2, r * 2)
                elif ctype == 'T-shape':
                    painter.setBrush(p_brush_color)
                    if gap <= 0:
                        painter.drawLine(int(-size), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, 0)
                    else:
                        painter.drawLine(int(-size), 0, int(-gap), 0)
                        painter.drawLine(int(gap), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, int(-gap))
                elif ctype == 'square':
                    painter.setBrush(Qt.NoBrush)
                    s = int(size)
                    painter.drawRect(-s, -s, s * 2, s * 2)
                elif ctype == 'diamond':
                    painter.setBrush(Qt.NoBrush)
                    s = int(size)
                    painter.save()
                    painter.rotate(45)
                    painter.drawRect(-s, -s, s * 2, s * 2)
                    painter.restore()

            if has_outline:
                outline_pen = QPen(QColor(0, 0, 0))
                outline_pen.setWidth(base_width + outline_thickness * 2)
                draw_preview_shapes(outline_pen, QColor(0, 0, 0))

            main_pen = QPen(color)
            main_pen.setWidth(base_width)
            draw_preview_shapes(main_pen, color)
                
        painter.end()
        self.preview_box.setPixmap(canvas)

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

# ============================================================
# CLASSIC UI IMPLEMENTATION (from gemini-code-1788555438822.py)
# ============================================================

import os
import math
os.environ["QT_QPA_PLATFORM"] = "xcb"

import sys
import shutil
import ctypes
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, 
    QVBoxLayout, QHBoxLayout, QSlider, QFrame, QFileDialog, 
    QColorDialog, QGridLayout, QScrollArea,
    QSizePolicy, QComboBox, QFormLayout, QStackedWidget,
    QGraphicsOpacityEffect, QTextEdit
)
from PyQt5.QtCore import Qt, QUrl, QTimer, pyqtSignal, pyqtProperty, QPropertyAnimation, QEasingCurve, QPoint
from PyQt5.QtGui import QPainter, QPen, QColor, QPixmap, QIcon, QDesktopServices, QGuiApplication


class OldAnimatedToggle(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(46, 24)
        self.setCursor(Qt.PointingHandCursor)
        
        self._circle_position = 3
        self.animation = QPropertyAnimation(self, b"circle_position", self)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setDuration(150)
        
        self.clicked.connect(self.start_animation)

    def get_circle_position(self):
        return self._circle_position

    def set_circle_position(self, pos):
        self._circle_position = pos
        self.update()

    circle_position = pyqtProperty(int, get_circle_position, set_circle_position)

    def start_animation(self, checked):
        if hasattr(self.window(), 'global_anim_mode') and self.window().global_anim_mode == 3:
            self.animation.setDuration(0)
        else:
            self.animation.setDuration(150)

        self.animation.stop()
        if checked:
            self.animation.setStartValue(3)
            self.animation.setEndValue(25)
        else:
            self.animation.setStartValue(25)
            self.animation.setEndValue(3)
        self.animation.start()

    def setChecked(self, checked):
        super().setChecked(checked)
        self._circle_position = 25 if checked else 3
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        
        if self.isChecked():
            bg_color = QColor(self.window().ui_accent_color) if hasattr(self.window(), 'ui_accent_color') else QColor(99, 102, 241)
        else:
            bg_color = QColor(31, 35, 48)
            
        p.setPen(Qt.NoPen)
        p.setBrush(bg_color)
        p.drawRoundedRect(0, 0, 46, 24, 12, 12)
        
        p.setBrush(QColor(255, 255, 255))
        p.drawEllipse(int(self._circle_position), 3, 18, 18)
        p.end()


class OldCrosshairOverlay(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        
        platform = QGuiApplication.platformName()
        flags = Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool
        
        if platform == 'wayland':
            flags |= Qt.WindowTransparentForInput
        elif platform == 'xcb':
            flags |= Qt.X11BypassWindowManagerHint

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        
        if platform != 'wayland':
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.setFixedSize(screen.size())

        self.anim_tick = 0
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.on_anim_frame)
        self.timer.start()

    def on_anim_frame(self):
        if self.main_window.animation_mode != 'none':
            self.anim_tick += 1
            self.update()

    def apply_x11_input_passthrough(self):
        try:
            if QGuiApplication.platformName() != 'xcb':
                return
            x11 = ctypes.CDLL("libX11.so.6")
            xfixes = ctypes.CDLL("libXfixes.so.3")
            display = x11.XOpenDisplay(None)
            if display:
                window_id = int(self.winId())
                if window_id:
                    region = xfixes.XFixesCreateRegion(display, None, 0)
                    xfixes.XFixesSetWindowShapeRegion(display, window_id, 2, 0, 0, region)
                    xfixes.XFixesDestroyRegion(display, region)
                    x11.XFlush(display)
                x11.XCloseDisplay(display)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        if QGuiApplication.platformName() == 'xcb':
            QTimer.singleShot(50, self.apply_x11_input_passthrough)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        cx = self.width() // 2
        cy = self.height() // 2
        
        size = float(self.main_window.size_val)
        gap = float(self.main_window.gap_val)
        color = self.main_window.color_val
        rotation = float(self.main_window.rotation_val)
        opacity = self.main_window.opacity_val / 100.0
        has_outline = self.main_window.outline_val
        outline_thickness = self.main_window.outline_thickness_val
        
        anim_mode = self.main_window.animation_mode
        anim_speed = self.main_window.animation_speed_val / 10.0
        
        if anim_mode == 'pulse':
            factor = 1.0 + 0.25 * math.sin(self.anim_tick * 0.08 * anim_speed)
            size *= factor
        elif anim_mode == 'spin':
            rotation += (self.anim_tick * 2.0 * anim_speed) % 360
        elif anim_mode == 'breathing':
            alpha_factor = 0.5 + 0.5 * math.sin(self.anim_tick * 0.06 * anim_speed)
            opacity *= max(0.2, alpha_factor)
        elif anim_mode == 'wave':
            gap += abs(6.0 * math.sin(self.anim_tick * 0.1 * anim_speed))

        painter.setOpacity(max(0.0, min(1.0, opacity)))
        
        if self.main_window.selected_builtin.startswith('custom_'):
            pixmap = self.main_window.custom_pixmaps.get(self.main_window.selected_builtin)
            if pixmap and not pixmap.isNull():
                pix = pixmap.scaled(int(size * 4), int(size * 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                if rotation != 0:
                    painter.translate(cx, cy)
                    painter.rotate(rotation)
                    painter.drawPixmap(-pix.width() // 2, -pix.height() // 2, pix)
                else:
                    painter.drawPixmap(cx - pix.width() // 2, cy - pix.height() // 2, pix)
                painter.end()
                return

        base_width = max(1, int(size // 5))
        
        def draw_shapes(p_pen, p_brush_color):
            painter.setPen(p_pen)
            painter.translate(cx, cy)
            painter.rotate(rotation)
            
            ctype = self.main_window.selected_builtin
            if ctype == 'cross':
                painter.setBrush(p_brush_color)
                if gap <= 0:
                    painter.drawLine(int(-size), 0, int(size), 0)
                    painter.drawLine(0, int(-size), 0, int(size))
                else:
                    painter.drawLine(int(-size), 0, int(-gap), 0)
                    painter.drawLine(int(gap), 0, int(size), 0)
                    painter.drawLine(0, int(-size), 0, int(-gap))
                    painter.drawLine(0, int(gap), 0, int(size))
            elif ctype == 'dot':
                painter.setBrush(p_brush_color)
                r = max(2, int(size // 3))
                painter.drawEllipse(-r, -r, r * 2, r * 2)
            elif ctype == 'circle':
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(int(-size), int(-size), int(size * 2), int(size * 2))
            elif ctype == 'cross_circle':
                painter.setBrush(p_brush_color)
                if gap <= 0:
                    painter.drawLine(int(-size), 0, int(size), 0)
                    painter.drawLine(0, int(-size), 0, int(size))
                else:
                    painter.drawLine(int(-size), 0, int(-gap), 0)
                    painter.drawLine(int(gap), 0, int(size), 0)
                    painter.drawLine(0, int(-size), 0, int(-gap))
                    painter.drawLine(0, int(gap), 0, int(size))
                painter.setBrush(Qt.NoBrush)
                r = int(size // 2)
                painter.drawEllipse(-r, -r, r * 2, r * 2)
            elif ctype == 'T-shape':
                painter.setBrush(p_brush_color)
                if gap <= 0:
                    painter.drawLine(int(-size), 0, int(size), 0)
                    painter.drawLine(0, int(-size), 0, 0)
                else:
                    painter.drawLine(int(-size), 0, int(-gap), 0)
                    painter.drawLine(int(gap), 0, int(size), 0)
                    painter.drawLine(0, int(-size), 0, int(-gap))
            painter.resetTransform()

        if has_outline:
            outline_pen = QPen(QColor(0, 0, 0))
            outline_pen.setWidth(base_width + outline_thickness * 2)
            draw_shapes(outline_pen, QColor(0, 0, 0))

        main_pen = QPen(color)
        main_pen.setWidth(base_width)
        draw_shapes(main_pen, color)
            
        painter.end()


class OldCrosshairCard(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, ctype, name, icon_pixmap, main_window, parent=None):
        super().__init__(parent)
        self.ctype = ctype
        self.main_window = main_window
        self.is_checked = False
        
        self.setObjectName("CrosshairCardFrame")
        self.setFixedSize(240, 100)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)

        self.icon_lbl = QLabel()
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_lbl.setPixmap(icon_pixmap.scaled(60, 35, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(self.icon_lbl, alignment=Qt.AlignHCenter)

        self.text_lbl = QLabel(name)
        self.text_lbl.setAlignment(Qt.AlignCenter)
        self.text_lbl.setStyleSheet("font-weight: 600; font-size: 13px; background: transparent;")
        layout.addWidget(self.text_lbl, alignment=Qt.AlignHCenter)

        self.update_style()

    def setChecked(self, checked):
        self.is_checked = checked
        self.update_style()

    def update_style(self):
        accent = self.main_window.ui_accent_color
        bg = self.main_window.ui_sidebar_color
        text_color = self.main_window.ui_text_color
        
        self.text_lbl.setStyleSheet(f"color: {text_color}; font-weight: 600; font-size: 13px; background: transparent;")
        
        if self.is_checked:
            self.setStyleSheet(f"""
                QFrame#CrosshairCardFrame {{
                    background-color: {bg};
                    border: 2px solid {accent};
                    border-radius: 10px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#CrosshairCardFrame {{
                    background-color: {self.main_window.ui_bg_color};
                    border: 1px solid #2d3348;
                    border-radius: 10px;
                }}
                QFrame#CrosshairCardFrame:hover {{
                    border-color: {accent};
                }}
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.ctype)


class OldSettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Dilates Crosshair Overlay')
        self.setFixedSize(880, 640)

        icon_path = os.path.join(os.path.dirname(__file__), 'crosshair.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            QApplication.setWindowIcon(QIcon(icon_path))

        config_dir = os.path.join(os.path.expanduser('~'), '.config', 'dilates-crosshair')
        self.custom_dir = os.path.join(config_dir, 'saved_custom_crosshairs')
        os.makedirs(self.custom_dir, exist_ok=True)

        self.selected_builtin = 'cross'
        self.custom_pixmaps = {} 
        self.choice_cards = {} 

        self.size_val = 14
        self.gap_val = 2
        self.color_val = QColor(0, 255, 100)
        self.rotation_val = 0
        self.opacity_val = 100
        self.outline_val = False
        self.outline_thickness_val = 1
        
        self.animation_mode = 'none' 
        self.animation_speed_val = 10
        
        self.global_anim_mode = 0  
        self.global_anim_duration = 220  
        self.global_anim_delay = 0       
        self.global_easing_curve = QEasingCurve.OutBounce  

        self.overlay_active = False
        self.overlay = None

        self.ui_bg_color = "#12141c"
        self.ui_sidebar_color = "#181b25"
        self.ui_accent_color = "#6366f1"
        self.ui_text_color = "#e5e7eb"

        self.load_saved_customs()
        self.initUI()

    def load_saved_customs(self):
        if not os.path.exists(self.custom_dir):
            return
        for file_name in os.listdir(self.custom_dir):
            if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                full_path = os.path.join(self.custom_dir, file_name)
                key = f"custom_{file_name}"
                pix = QPixmap(full_path)
                if not pix.isNull():
                    self.custom_pixmaps[key] = pix

    def apply_stylesheet(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {self.ui_bg_color};
                color: {self.ui_text_color};
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }}
            QFrame#Sidebar {{
                background-color: {self.ui_sidebar_color};
                border-right: 1px solid #222634;
            }}
            QFrame#Card {{
                background-color: {self.ui_sidebar_color};
                border: 1px solid #222634;
                border-radius: 8px;
            }}
            QPushButton#SidebarBtn {{
                background-color: {self.ui_bg_color};
                border: 1px solid #2d3348;
                border-radius: 6px;
                padding: 8px 14px;
                color: {self.ui_text_color};
                text-align: left;
                font-weight: 500;
            }}
            QPushButton#SidebarBtn:hover {{
                border-color: {self.ui_accent_color};
            }}
            QPushButton#SidebarBtn:checked {{
                background-color: {self.ui_sidebar_color};
                border: 1px solid {self.ui_accent_color};
            }}
            QPushButton#ActionBtn {{
                background-color: {self.ui_accent_color};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: bold;
            }}
            QComboBox, QLineEdit, QTextEdit {{
                background-color: {self.ui_bg_color};
                border: 1px solid #2d3348;
                border-radius: 6px;
                padding: 6px 10px;
                color: {self.ui_text_color};
            }}
            QSlider::groove:horizontal {{
                border: none;
                height: 6px;
                background: #1f2330;
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {self.ui_accent_color};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: #ffffff;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }}
        """)
        
        for ctype, card in self.choice_cards.items():
            card.update_style()
            
        if hasattr(self, 'outline_toggle'):
            self.outline_toggle.update()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(210)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(15, 20, 15, 20)
        sidebar_layout.setSpacing(8)

        logo_label = QLabel("DilatesCross")
        logo_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        sidebar_layout.addWidget(logo_label)

        self.btn_tab_main = self.create_nav_btn("🎯 Прицелы", 0, True)
        self.btn_tab_code = self.create_nav_btn("🌐 Сайты с PNG", 1, False)
        self.btn_tab_custom = self.create_nav_btn("🖼️ Загрузить PNG", 2, False)
        self.btn_tab_settings = self.create_nav_btn("⚙️ Настройки", 3, False)
        self.btn_tab_ui = self.create_nav_btn("🎨 Интерфейс", 4, False)
        self.btn_tab_export = self.create_nav_btn("🛠️ Экспорт/Импорт", 5, False)
        self.btn_tab_about = self.create_nav_btn("ℹ️ О программе", 6, False)

        sidebar_layout.addWidget(self.btn_tab_main)
        sidebar_layout.addWidget(self.btn_tab_code)
        sidebar_layout.addWidget(self.btn_tab_custom)
        sidebar_layout.addWidget(self.btn_tab_settings)
        sidebar_layout.addWidget(self.btn_tab_ui)
        sidebar_layout.addWidget(self.btn_tab_export)
        sidebar_layout.addWidget(self.btn_tab_about)
        sidebar_layout.addStretch()

        self.toggle_btn = QPushButton("OVERLAY OFF")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setStyleSheet("""
            QPushButton { background-color: #7f1d1d; color: #fca5a5; border: none; font-weight: bold; text-align: center; padding: 10px; border-radius: 6px; }
            QPushButton:checked { background-color: #14532d; color: #86efac; border: none; }
        """)
        self.toggle_btn.clicked.connect(self.toggle_overlay)
        sidebar_layout.addWidget(self.toggle_btn)

        main_layout.addWidget(self.sidebar)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("background: transparent;")
        
        self.pages = [
            self.create_crosshairs_page(),
            self.create_code_page(),
            self.create_custom_page(),
            self.create_settings_page(),
            self.create_ui_settings_page(),
            self.create_export_page(),
            self.create_about_page()
        ]

        for p in self.pages:
            self.stacked_widget.addWidget(p)

        wrapper_widget = QWidget()
        wrapper_layout = QVBoxLayout(wrapper_widget)
        wrapper_layout.setContentsMargins(15, 15, 15, 15)
        wrapper_layout.addWidget(self.stacked_widget)

        main_layout.addWidget(wrapper_widget)
        
        self.apply_stylesheet()
        self.update_preview()
        
        self.switch_tab(0)

    def create_nav_btn(self, text, index, checked):
        btn = QPushButton(text)
        btn.setObjectName("SidebarBtn")
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.clicked.connect(lambda: self.switch_tab(index))
        return btn

    def switch_tab(self, index):
        self.stacked_widget.setCurrentIndex(index)
        
        nav_btns = [
            self.btn_tab_main, self.btn_tab_code, self.btn_tab_custom, 
            self.btn_tab_settings, self.btn_tab_ui, self.btn_tab_export, self.btn_tab_about
        ]
        for i, btn in enumerate(nav_btns):
            btn.setChecked(i == index)
            
        current_page = self.pages[index]
        current_page.setGraphicsEffect(None)
        current_page.move(0, 0)
        
        if self.global_anim_mode == 3:
            return

        delay = self.global_anim_delay
        if delay > 0:
            QTimer.singleShot(delay, lambda: self.start_page_animation(current_page))
        else:
            self.start_page_animation(current_page)

    def start_page_animation(self, current_page):
        dur = self.global_anim_duration
        curve = self.global_easing_curve

        if self.global_anim_mode == 0: # Плавный отскок (Bounce)
            self.fade_effect = QGraphicsOpacityEffect(current_page)
            current_page.setGraphicsEffect(self.fade_effect)
            
            self.anim_opacity = QPropertyAnimation(self.fade_effect, b"opacity", self)
            self.anim_opacity.setDuration(dur)
            self.anim_opacity.setStartValue(0.0)
            self.anim_opacity.setEndValue(1.0)
            
            self.anim_pos = QPropertyAnimation(current_page, b"pos", self)
            self.anim_pos.setDuration(dur)
            self.anim_pos.setStartValue(QPoint(0, 30))
            self.anim_pos.setEndValue(QPoint(0, 0))
            self.anim_pos.setEasingCurve(curve)
            
            self.anim_opacity.start()
            self.anim_pos.start()

        elif self.global_anim_mode == 1: # Плавное затухание (Fade In)
            self.fade_effect = QGraphicsOpacityEffect(current_page)
            current_page.setGraphicsEffect(self.fade_effect)
            
            self.page_anim = QPropertyAnimation(self.fade_effect, b"opacity", self)
            self.page_anim.setDuration(dur)
            self.page_anim.setStartValue(0.0)
            self.page_anim.setEndValue(1.0)
            self.page_anim.setEasingCurve(curve)
            self.page_anim.start()

        elif self.global_anim_mode == 2: # Плавный скок снизу (Slide Up)
            self.fade_effect = QGraphicsOpacityEffect(current_page)
            current_page.setGraphicsEffect(self.fade_effect)
            
            self.anim_opacity = QPropertyAnimation(self.fade_effect, b"opacity", self)
            self.anim_opacity.setDuration(dur)
            self.anim_opacity.setStartValue(0.0)
            self.anim_opacity.setEndValue(1.0)
            
            self.anim_pos = QPropertyAnimation(current_page, b"pos", self)
            self.anim_pos.setDuration(dur)
            self.anim_pos.setStartValue(QPoint(0, 45))
            self.anim_pos.setEndValue(QPoint(0, 0))
            self.anim_pos.setEasingCurve(curve)
            
            self.anim_opacity.start()
            self.anim_pos.start()

    def generate_crosshair_preview_pixmap(self, ctype):
        canvas = QPixmap(120, 50)
        canvas.fill(Qt.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        cx, cy = 60, 25
        size = 12  
        color = QColor(self.ui_text_color)
        
        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)
        
        if ctype == 'cross':
            painter.setBrush(color)
            painter.drawLine(cx - size, cy, cx + size, cy)
            painter.drawLine(cx, cy - size, cx, cy + size)
        elif ctype == 'dot':
            painter.setBrush(color)
            painter.drawEllipse(cx - 3, cy - 3, 6, 6)
        elif ctype == 'circle':
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(cx - size, cy - size, size * 2, size * 2)
        elif ctype == 'cross_circle':
            painter.setBrush(color)
            painter.drawLine(cx - size, cy, cx + size, cy)
            painter.drawLine(cx, cy - size, cx, cy + size)
            painter.setBrush(Qt.NoBrush)
            r = size // 2
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        elif ctype == 'T-shape':
            painter.setBrush(color)
            painter.drawLine(cx - size, cy, cx + size, cy)
            painter.drawLine(cx, cy - size, cx, cy)
            
        painter.end()
        return canvas

    def create_crosshairs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(QLabel("<b>Все доступные прицелы</b>", styleSheet="font-size: 15px;"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        grid = QGridLayout(container)
        grid.setSpacing(15)
        grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.choice_cards.clear()

        builtins = [
            ('cross', 'Крест'),
            ('dot', 'Точка'),
            ('circle', 'Круг'),
            ('cross_circle', 'Кольцо'),
            ('T-shape', 'Т-образный')
        ]

        row, col = 0, 0
        for ctype, name in builtins:
            pix = self.generate_crosshair_preview_pixmap(ctype)
            card = OldCrosshairCard(ctype, name, pix, self)
            card.setChecked(ctype == self.selected_builtin)
            card.clicked.connect(self.select_builtin)
            
            grid.addWidget(card, row, col)
            self.choice_cards[ctype] = card
            col += 1
            if col > 1:
                col = 0
                row += 1

        for key, pixmap in self.custom_pixmaps.items():
            display_name = key.replace("custom_", "")
            if len(display_name) > 16:
                display_name = display_name[:13] + "..."
            
            card = OldCrosshairCard(key, display_name, pixmap, self)
            card.setChecked(key == self.selected_builtin)
            card.clicked.connect(self.select_builtin)
            
            grid.addWidget(card, row, col)
            self.choice_cards[key] = card
            col += 1
            if col > 1:
                col = 0
                row += 1

        grid.setRowStretch(row + 1, 1)
        grid.setColumnStretch(2, 1)

        scroll.setWidget(container)
        layout.addWidget(scroll)
        return page

    def create_code_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        layout.addWidget(QLabel("<b>Каталоги иконок прицелов (PNG)</b>", styleSheet="font-size: 15px;"))
        layout.addWidget(QLabel("Используйте проверенные сайты для скачивания иконок и картинок прицелов в формате PNG:", styleSheet="color: #9ca3af;"))

        btn_site1 = QPushButton("🌐 Открыть Icons8 (Прицел)")
        btn_site1.setObjectName("ActionBtn")
        btn_site1.setMinimumHeight(42)
        btn_site1.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://icons8.ru/icons/set/%D0%BF%D1%80%D0%B8%D1%86%D0%B5%D0%BB")))
        layout.addWidget(btn_site1)

        btn_site2 = QPushButton("🌐 Открыть Flaticon (Crosshair)")
        btn_site2.setObjectName("ActionBtn")
        btn_site2.setMinimumHeight(42)
        btn_site2.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.flaticon.com/free-icons/crosshair")))
        layout.addWidget(btn_site2)

        layout.addSpacing(10)
        info_label = QLabel(
            "💡 <b>Инструкция:</b> Перейдите на один из сайтов по кнопкам выше, выберите нужную иконку, "
            "скачайте её в формате PNG (желательно с прозрачным фоном), а затем загрузите полученный файл во вкладке <b>«Загрузить PNG»</b>."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #9ca3af; background-color: #181b25; padding: 12px; border-radius: 8px; border: 1px solid #2d3348;")
        layout.addWidget(info_label)

        layout.addStretch()
        return page

    def refresh_crosshairs_grid(self):
        old_page = self.pages[0]
        new_page = self.create_crosshairs_page()
        
        self.stacked_widget.removeWidget(old_page)
        self.pages[0] = new_page
        self.stacked_widget.insertWidget(0, new_page)
        
        if self.stacked_widget.currentIndex() == 0:
            self.switch_tab(0)
        old_page.deleteLater()

    def select_builtin(self, ctype):
        self.selected_builtin = ctype
        for t, card in self.choice_cards.items():
            card.setChecked(t == ctype)
        self.on_setting_changed()

    def create_custom_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        layout.addWidget(QLabel("<b>Загрузка пользовательских картинок (PNG)</b>", styleSheet="font-size: 15px;"))
        layout.addWidget(QLabel("Если вы хотите использовать собственное изображение прицела в виде текстуры:", styleSheet="color: #9ca3af;"))

        btn_load = QPushButton("📁 Выбрать PNG файл и сохранить")
        btn_load.setObjectName("ActionBtn")
        btn_load.clicked.connect(self.load_custom_png)
        layout.addWidget(btn_load)

        layout.addStretch()
        return page

    def load_custom_png(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать PNG прицел", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            file_name = os.path.basename(path)
            dest_path = os.path.join(self.custom_dir, file_name)
            
            if not os.path.exists(dest_path) or os.path.abspath(path) != os.path.abspath(dest_path):
                shutil.copy(path, dest_path)
            
            pix = QPixmap(dest_path)
            if not pix.isNull():
                key = f"custom_{file_name}"
                self.custom_pixmaps[key] = pix
                self.selected_builtin = key
                
                self.refresh_crosshairs_grid()
                self.on_setting_changed()
                self.switch_tab(0)

    def create_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        layout.addWidget(QLabel("<b>Параметры прицела</b>", styleSheet="font-size: 14px;"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(15, 12, 15, 12)
        card_layout.setSpacing(8)

        card_layout.addWidget(QLabel("Размер (Size)"))
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(4, 50)
        self.size_slider.setValue(self.size_val)
        self.size_slider.valueChanged.connect(self.on_setting_changed)
        card_layout.addWidget(self.size_slider)

        card_layout.addWidget(QLabel("Центральный зазор (Gap)"))
        self.gap_slider = QSlider(Qt.Horizontal)
        self.gap_slider.setRange(0, 20)
        self.gap_slider.setValue(self.gap_val)
        self.gap_slider.valueChanged.connect(self.on_setting_changed)
        card_layout.addWidget(self.gap_slider)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Цвет прицела"))
        self.color_btn = QPushButton("Выбрать цвет")
        self.color_btn.setObjectName("SidebarBtn")
        self.color_btn.setMinimumWidth(165)
        self.color_btn.setFixedHeight(32)
        self.update_color_btn_style()
        self.color_btn.clicked.connect(self.open_color_dialog)
        color_row.addWidget(self.color_btn)
        color_row.addStretch()
        card_layout.addLayout(color_row)

        card_layout.addWidget(QLabel("Вращение (Rotation)"))
        self.rot_slider = QSlider(Qt.Horizontal)
        self.rot_slider.setRange(0, 360)
        self.rot_slider.setValue(self.rotation_val)
        self.rot_slider.valueChanged.connect(self.on_setting_changed)
        card_layout.addWidget(self.rot_slider)

        card_layout.addWidget(QLabel("Прозрачность (Opacity)"))
        self.op_slider = QSlider(Qt.Horizontal)
        self.op_slider.setRange(10, 100)
        self.op_slider.setValue(self.opacity_val)
        self.op_slider.valueChanged.connect(self.on_setting_changed)
        card_layout.addWidget(self.op_slider)

        anim_row = QHBoxLayout()
        anim_row.addWidget(QLabel("Анимация оверлея прицела"))
        self.anim_combo = QComboBox()
        self.anim_combo.addItems([
            "Без анимации (Откл)", 
            "1. Пульсация (Pulse)", 
            "2. Вращение (Spin)", 
            "3. Дыхание (Breathing)", 
            "4. Волна (Wave Gap)"
        ])
        self.anim_combo.setMinimumWidth(180)
        self.anim_combo.currentIndexChanged.connect(self.on_animation_changed)
        anim_row.addWidget(self.anim_combo)
        anim_row.addStretch()
        card_layout.addLayout(anim_row)

        card_layout.addWidget(QLabel("Скорость анимации прицела"))
        self.anim_speed_slider = QSlider(Qt.Horizontal)
        self.anim_speed_slider.setRange(2, 30)
        self.anim_speed_slider.setValue(self.animation_speed_val)
        self.anim_speed_slider.valueChanged.connect(self.on_setting_changed)
        card_layout.addWidget(self.anim_speed_slider)

        outline_row = QHBoxLayout()
        self.outline_toggle = OldAnimatedToggle()
        self.outline_toggle.setChecked(self.outline_val)
        self.outline_toggle.clicked.connect(self.on_setting_changed)
        
        outline_row.addWidget(self.outline_toggle)
        outline_row.addWidget(QLabel("Включить черную обводку (Outline)"))
        outline_row.addStretch()
        card_layout.addLayout(outline_row)

        card_layout.addWidget(QLabel("Толщина обводки"))
        self.outline_thick_slider = QSlider(Qt.Horizontal)
        self.outline_thick_slider.setRange(1, 5)
        self.outline_thick_slider.setValue(self.outline_thickness_val)
        self.outline_thick_slider.valueChanged.connect(self.on_setting_changed)
        card_layout.addWidget(self.outline_thick_slider)

        scroll.setWidget(card)
        layout.addWidget(scroll)

        self.preview_box = QLabel()
        self.preview_box.setFixedHeight(60)
        self.preview_box.setAlignment(Qt.AlignCenter)
        self.preview_box.setStyleSheet("background-color: #0d0f17; border-radius: 6px; border: 1px solid #222634;")
        layout.addWidget(self.preview_box)

        return page

    def create_ui_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(15)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(24) 

        # --- ГРУППА 1: НАСТРОЙКИ ИНТЕРФЕЙСА ---
        ui_card = QFrame()
        ui_card.setObjectName("Card")
        ui_card_layout = QVBoxLayout(ui_card)
        ui_card_layout.setContentsMargins(15, 15, 15, 15)
        ui_card_layout.setSpacing(12)

        ui_card_layout.addWidget(QLabel("<b>🎨 Настройки интерфейса</b>", styleSheet="font-size: 14px; color: #a5b4fc; margin-bottom: 4px;"))

        ui_form = QFormLayout()
        ui_form.setSpacing(12)
        ui_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.theme_combo = QComboBox()
        themes = [
            "Темная классическая (Cyber)",
            "Темный углерод (Dark Carbon)",
            "Светлая минималистичная",
            "Неоновая фиолетовая",
            "Кровавая луна (Red)",
            "Хакерская (Matrix)",
            "Океанская бездна (Blue)"
        ]
        self.theme_combo.addItems(themes)
        self.theme_combo.setMinimumHeight(32)
        self.theme_combo.currentIndexChanged.connect(self.change_ui_theme)
        ui_form.addRow("Готовые цветовые темы:", self.theme_combo)

        self.ui_accent_btn = QPushButton("ВЫБРАТЬ ЦВЕТ")
        self.ui_accent_btn.setObjectName("ActionBtn")
        self.ui_accent_btn.setMinimumHeight(32)
        self.ui_accent_btn.clicked.connect(self.open_ui_accent_dialog)
        ui_form.addRow("Акцентный цвет интерфейса:", self.ui_accent_btn)

        ui_card_layout.addLayout(ui_form)
        scroll_layout.addWidget(ui_card)

        # --- ГРУППА 2: НАСТРОЙКИ АНИМАЦИИ ---
        anim_card = QFrame()
        anim_card.setObjectName("Card")
        anim_card_layout = QVBoxLayout(anim_card)
        anim_card_layout.setContentsMargins(15, 15, 15, 15)
        anim_card_layout.setSpacing(12)

        anim_card_layout.addWidget(QLabel("<b>✨ Настройки анимации</b>", styleSheet="font-size: 14px; color: #a5b4fc; margin-bottom: 4px;"))

        anim_form = QFormLayout()
        anim_form.setSpacing(12)
        anim_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.global_anim_combo = QComboBox()
        global_animations = [
            "1. Плавный отскок (Bounce)",
            "2. Плавное затухание (Fade)",
            "3. Плавный скок снизу (Slide Up)",
            "4. Отключить анимации полностью"
        ]
        self.global_anim_combo.addItems(global_animations)
        self.global_anim_combo.setCurrentIndex(self.global_anim_mode)
        self.global_anim_combo.setMinimumHeight(32)
        self.global_anim_combo.currentIndexChanged.connect(self.change_global_animation_mode)
        anim_form.addRow("Переключатель анимаций интерфейса:", self.global_anim_combo)

        self.anim_duration_slider = QSlider(Qt.Horizontal)
        self.anim_duration_slider.setRange(50, 800)
        self.anim_duration_slider.setValue(self.global_anim_duration)
        self.anim_duration_slider.setSingleStep(10)
        self.anim_duration_slider.valueChanged.connect(self.change_global_animation_duration)
        self.anim_duration_label = QLabel(f"{self.global_anim_duration} мс")
        self.anim_duration_label.setStyleSheet("font-weight: bold; color: #a5b4fc;")
        
        dur_row = QHBoxLayout()
        dur_row.addWidget(self.anim_duration_slider)
        dur_row.addWidget(self.anim_duration_label)
        anim_form.addRow("Длительность переходов:", dur_row)

        self.anim_delay_slider = QSlider(Qt.Horizontal)
        self.anim_delay_slider.setRange(0, 300)
        self.anim_delay_slider.setValue(self.global_anim_delay)
        self.anim_delay_slider.setSingleStep(10)
        self.anim_delay_slider.valueChanged.connect(self.change_global_animation_delay)
        self.anim_delay_label = QLabel(f"{self.global_anim_delay} мс")
        self.anim_delay_label.setStyleSheet("font-weight: bold; color: #a5b4fc;")
        
        delay_row = QHBoxLayout()
        delay_row.addWidget(self.anim_delay_slider)
        delay_row.addWidget(self.anim_delay_label)
        anim_form.addRow("Задержка перед анимацией (Delay):", delay_row)

        anim_card_layout.addLayout(anim_form)
        scroll_layout.addWidget(anim_card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        return page

    def create_export_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(QLabel("<b>Экспорт и импорт настроек конфигурации</b>", styleSheet="font-size: 15px;"))
        layout.addWidget(QLabel("Вы можете скопировать настройки текущего прицела в формате JSON или загрузить их обратно:", styleSheet="color: #9ca3af;"))

        self.config_text_area = QTextEdit()
        self.update_config_json_view()
        layout.addWidget(self.config_text_area)

        btn_row = QHBoxLayout()
        btn_copy = QPushButton("📋 Скопировать конфигурацию")
        btn_copy.setObjectName("ActionBtn")
        btn_copy.clicked.connect(self.copy_config_to_clipboard)
        
        btn_apply = QPushButton("📥 Применить из текста")
        btn_apply.setObjectName("ActionBtn")
        btn_apply.clicked.connect(self.apply_config_from_text)
        
        btn_row.addWidget(btn_copy)
        btn_row.addWidget(btn_apply)
        layout.addLayout(btn_row)

        return page

    def update_config_json_view(self):
        config_data = {
            "selected_builtin": self.selected_builtin,
            "size": self.size_val,
            "gap": self.gap_val,
            "color": self.color_val.name(),
            "rotation": self.rotation_val,
            "opacity": self.opacity_val,
            "outline": self.outline_val,
            "outline_thickness": self.outline_thickness_val,
            "animation_mode": self.animation_mode,
            "animation_speed": self.animation_speed_val
        }
        if hasattr(self, 'config_text_area'):
            self.config_text_area.setText(json.dumps(config_data, indent=4, ensure_ascii=False))

    def copy_config_to_clipboard(self):
        self.update_config_json_view()
        clipboard = QApplication.clipboard()
        clipboard.setText(self.config_text_area.toPlainText())

    def apply_config_from_text(self):
        try:
            data = json.loads(self.config_text_area.toPlainText())
            if "size" in data: self.size_val = data["size"]
            if "gap" in data: self.gap_val = data["gap"]
            if "color" in data: self.color_val = QColor(data["color"])
            if "rotation" in data: self.rotation_val = data["rotation"]
            if "opacity" in data: self.opacity_val = data["opacity"]
            if "outline" in data: self.outline_val = data["outline"]
            if "outline_thickness" in data: self.outline_thickness_val = data["outline_thickness"]
            if "animation_mode" in data: self.animation_mode = data["animation_mode"]
            if "animation_speed" in data: self.animation_speed_val = data["animation_speed"]
            if "selected_builtin" in data: self.selected_builtin = data["selected_builtin"]

            if hasattr(self, 'size_slider'): self.size_slider.setValue(self.size_val)
            if hasattr(self, 'gap_slider'): self.gap_slider.setValue(self.gap_val)
            if hasattr(self, 'rot_slider'): self.rot_slider.setValue(self.rotation_val)
            if hasattr(self, 'op_slider'): self.op_slider.setValue(self.opacity_val)
            if hasattr(self, 'anim_speed_slider'): self.anim_speed_slider.setValue(self.animation_speed_val)
            if hasattr(self, 'outline_toggle'): self.outline_toggle.setChecked(self.outline_val)
            if hasattr(self, 'outline_thick_slider'): self.outline_thick_slider.setValue(self.outline_thickness_val)
            self.update_color_btn_style()
            self.update_preview()
        except Exception:
            pass

    def create_about_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        layout.addWidget(QLabel("<b>О программе Dilates Crosshair</b>", styleSheet="font-size: 15px;"))
        
        info_card = QFrame()
        info_card.setObjectName("Card")
        info_card_layout = QVBoxLayout(info_card)
        info_card_layout.setContentsMargins(20, 20, 20, 20)
        info_card_layout.setSpacing(10)

        info_card_layout.addWidget(QLabel("<b>Версия:</b> 2.6.0 (Linux / X11 / Wayland Ready)"))
        info_card_layout.addWidget(QLabel("<b>Описание:</b> Профессиональный кроссхейр-оверлей с поддержкой кастомных текстур PNG, динамических анимаций и гибкой кастомизации интерфейса."))
        info_card_layout.addWidget(QLabel("<b>Горячая клавиша:</b> Управление оверлеем осуществляется с помощью кнопки слева в панели управления."))
        
        repo_btn = QPushButton("🌐 Открыть репозиторий проекта")
        repo_btn.setObjectName("ActionBtn")
        repo_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com")))
        info_card_layout.addWidget(repo_btn)

        layout.addWidget(info_card)
        layout.addStretch()
        return page

    def change_global_animation_mode(self, index):
        self.global_anim_mode = index
        
        # 4 оставшихся режима (масштабирование и линейный удалены)
        curves = [
            QEasingCurve.OutBounce, # 1. Плавный отскок
            QEasingCurve.InOutQuad, # 2. Плавное затухание
            QEasingCurve.OutCubic,  # 3. Плавный скок снизу
            QEasingCurve.Linear     # 4. Отключено
        ]
        if 0 <= index < len(curves):
            self.global_easing_curve = curves[index]

        is_enabled = index != 3
        if hasattr(self, 'anim_duration_slider'):
            self.anim_duration_slider.setEnabled(is_enabled)
        if hasattr(self, 'anim_delay_slider'):
            self.anim_delay_slider.setEnabled(is_enabled)

    def change_global_animation_duration(self, value):
        self.global_anim_duration = value
        if hasattr(self, 'anim_duration_label'):
            self.anim_duration_label.setText(f"{value} мс")

    def change_global_animation_delay(self, value):
        self.global_anim_delay = value
        if hasattr(self, 'anim_delay_label'):
            self.anim_delay_label.setText(f"{value} мс")

    def change_ui_theme(self, index):
        if index == 0: 
            self.ui_bg_color = "#12141c"
            self.ui_sidebar_color = "#181b25"
            self.ui_accent_color = "#6366f1"
            self.ui_text_color = "#e5e7eb"
        elif index == 1: 
            self.ui_bg_color = "#0a0a0a"
            self.ui_sidebar_color = "#141414"
            self.ui_accent_color = "#3b82f6"
            self.ui_text_color = "#f3f4f6"
        elif index == 2: 
            self.ui_bg_color = "#f3f4f6"
            self.ui_sidebar_color = "#ffffff"
            self.ui_accent_color = "#2563eb"
            self.ui_text_color = "#1f2937"
        elif index == 3: 
            self.ui_bg_color = "#110c1d"
            self.ui_sidebar_color = "#1a122c"
            self.ui_accent_color = "#a855f7"
            self.ui_text_color = "#f3e8ff"
        elif index == 4: 
            self.ui_bg_color = "#1a0b0b"
            self.ui_sidebar_color = "#2a1212"
            self.ui_accent_color = "#ef4444"
            self.ui_text_color = "#fecaca"
        elif index == 5: 
            self.ui_bg_color = "#050505"
            self.ui_sidebar_color = "#0a0a0a"
            self.ui_accent_color = "#22c55e"
            self.ui_text_color = "#bbf7d0"
        elif index == 6: 
            self.ui_bg_color = "#0f172a"
            self.ui_sidebar_color = "#1e293b"
            self.ui_accent_color = "#0ea5e9"
            self.ui_text_color = "#e0f2fe"
            
        self.apply_stylesheet()
        self.refresh_crosshairs_grid()

    def open_ui_accent_dialog(self):
        col = QColorDialog.getColor(QColor(self.ui_accent_color), self, "Выбор акцентного цвета")
        if col.isValid():
            self.ui_accent_color = col.name()
            self.apply_stylesheet()
            self.refresh_crosshairs_grid()

    def open_color_dialog(self):
        col = QColorDialog.getColor(self.color_val, self, "Выбор цвета прицела")
        if col.isValid():
            self.color_val = col
            self.update_color_btn_style()
            self.on_setting_changed()

    def update_color_btn_style(self):
        self.color_btn.setStyleSheet(f"background-color: {self.color_val.name()}; color: #000000; font-weight: bold; border-radius: 4px; padding: 0 10px;")

    def toggle_overlay(self, checked):
        self.overlay_active = checked
        if checked:
            self.toggle_btn.setText("OVERLAY ON")
            if not self.overlay:
                self.overlay = OldCrosshairOverlay(self)
            self.overlay.show()
        else:
            self.toggle_btn.setText("OVERLAY OFF")
            if self.overlay:
                self.overlay.hide()

    def on_animation_changed(self, index):
        modes = ['none', 'pulse', 'spin', 'breathing', 'wave']
        if 0 <= index < len(modes):
            self.animation_mode = modes[index]
        self.on_setting_changed()

    def on_setting_changed(self):
        self.size_val = self.size_slider.value() if hasattr(self, 'size_slider') else self.size_val
        self.gap_val = self.gap_slider.value() if hasattr(self, 'gap_slider') else self.gap_val
        self.rotation_val = self.rot_slider.value() if hasattr(self, 'rot_slider') else self.rotation_val
        self.opacity_val = self.op_slider.value() if hasattr(self, 'op_slider') else self.opacity_val
        self.animation_speed_val = self.anim_speed_slider.value() if hasattr(self, 'anim_speed_slider') else self.animation_speed_val
        self.outline_val = self.outline_toggle.isChecked() if hasattr(self, 'outline_toggle') else self.outline_val
        self.outline_thickness_val = self.outline_thick_slider.value() if hasattr(self, 'outline_thick_slider') else self.outline_thickness_val
        
        self.update_preview()
        self.update_config_json_view()
        if hasattr(self, 'overlay') and self.overlay:
            self.overlay.update()

    def update_preview(self):
        if not hasattr(self, 'preview_box'):
            return
        canvas = QPixmap(self.preview_box.size())
        canvas.fill(QColor(self.ui_sidebar_color))
        
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        opacity = self.opacity_val / 100.0
        painter.setOpacity(opacity)
        
        cx = canvas.width() // 2
        cy = canvas.height() // 2
        size = min(self.size_val, 22)
        gap = min(self.gap_val, size - 2)
        color = self.color_val
        rotation = self.rotation_val
        has_outline = self.outline_val
        outline_thickness = self.outline_thickness_val
        
        if self.selected_builtin.startswith('custom_'):
            pixmap = self.custom_pixmaps.get(self.selected_builtin)
            if pixmap and not pixmap.isNull():
                pix = pixmap.scaled(size * 3, size * 3, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                if rotation != 0:
                    painter.translate(cx, cy)
                    painter.rotate(rotation)
                    painter.drawPixmap(-pix.width() // 2, -pix.height() // 2, pix)
                else:
                    painter.drawPixmap(cx - pix.width() // 2, cy - pix.height() // 2, pix)
        else:
            base_width = max(1, size // 5)

            def draw_preview_shapes(p_pen, p_brush_color):
                painter.setPen(p_pen)
                painter.resetTransform()
                painter.translate(cx, cy)
                painter.rotate(rotation)
                
                ctype = self.selected_builtin
                if ctype == 'cross':
                    painter.setBrush(p_brush_color)
                    if gap <= 0:
                        painter.drawLine(int(-size), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, int(size))
                    else:
                        painter.drawLine(int(-size), 0, int(-gap), 0)
                        painter.drawLine(int(gap), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, int(-gap))
                        painter.drawLine(0, int(gap), 0, int(size))
                elif ctype == 'dot':
                    painter.setBrush(p_brush_color)
                    r = max(2, int(size // 3))
                    painter.drawEllipse(-r, -r, r * 2, r * 2)
                elif ctype == 'circle':
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(int(-size), int(-size), int(size * 2), int(size * 2))
                elif ctype == 'cross_circle':
                    painter.setBrush(p_brush_color)
                    if gap <= 0:
                        painter.drawLine(int(-size), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, int(size))
                    else:
                        painter.drawLine(int(-size), 0, int(-gap), 0)
                        painter.drawLine(int(gap), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, int(-gap))
                        painter.drawLine(0, int(gap), 0, int(size))
                    painter.setBrush(Qt.NoBrush)
                    r = int(size // 2)
                    painter.drawEllipse(-r, -r, r * 2, r * 2)
                elif ctype == 'T-shape':
                    painter.setBrush(p_brush_color)
                    if gap <= 0:
                        painter.drawLine(int(-size), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, 0)
                    else:
                        painter.drawLine(int(-size), 0, int(-gap), 0)
                        painter.drawLine(int(gap), 0, int(size), 0)
                        painter.drawLine(0, int(-size), 0, int(-gap))

            if has_outline:
                outline_pen = QPen(QColor(0, 0, 0))
                outline_pen.setWidth(base_width + outline_thickness * 2)
                draw_preview_shapes(outline_pen, QColor(0, 0, 0))

            main_pen = QPen(color)
            main_pen.setWidth(base_width)
            draw_preview_shapes(main_pen, color)
                
        painter.end()
        self.preview_box.setPixmap(canvas)


# ============================================================
# MERGED UI SWITCHER
# ============================================================

class MergedSettingsWindow(QMainWindow):
    """Hosts both original interfaces and lets the user switch between them."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dilates Crosshair Overlay — UI Switcher")
        self.setFixedSize(960, 735)

        self.new_ui = SettingsWindow()
        self.old_ui = OldSettingsWindow()

        # These windows become child widgets of the stacked interface.
        for child in (self.new_ui, self.old_ui):
            child.setWindowFlags(Qt.Widget)
            child.setMinimumSize(0, 0)
            child.setMaximumSize(16777215, 16777215)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Compact switch bar — this is the control used to change the UI.
        switch_bar = QFrame()
        switch_bar.setObjectName("MergedSwitchBar")
        switch_layout = QHBoxLayout(switch_bar)
        switch_layout.setContentsMargins(10, 6, 10, 6)
        switch_layout.setSpacing(8)

        title = QLabel("Dilates Crosshair")
        title.setStyleSheet("font-size: 14px; font-weight: 700;")
        switch_layout.addWidget(title)

        switch_layout.addStretch()

        self.ui_mode_label = QLabel("Интерфейс: Новый")
        self.ui_mode_label.setStyleSheet("font-size: 12px; font-weight: 600;")
        switch_layout.addWidget(self.ui_mode_label)

        self.ui_switch = QPushButton("Новый")
        self.ui_switch.setCheckable(True)
        self.ui_switch.setChecked(True)
        self.ui_switch.setMinimumWidth(110)
        self.ui_switch.setToolTip("Переключить между новым и классическим интерфейсом")
        self.ui_switch.clicked.connect(self.switch_ui)
        switch_layout.addWidget(self.ui_switch)

        root.addWidget(switch_bar)

        self.interface_stack = QStackedWidget()
        root.addWidget(self.interface_stack, 1)

        # Center each original UI inside the switcher.
        new_page = QWidget()
        new_layout = QVBoxLayout(new_page)
        new_layout.setContentsMargins(0, 0, 0, 0)
        new_layout.setAlignment(Qt.AlignCenter)
        new_layout.addWidget(self.new_ui)

        old_page = QWidget()
        old_layout = QVBoxLayout(old_page)
        old_layout.setContentsMargins(0, 0, 0, 0)
        old_layout.setAlignment(Qt.AlignCenter)
        old_layout.addWidget(self.old_ui)

        self.interface_stack.addWidget(new_page)
        self.interface_stack.addWidget(old_page)
        self.interface_stack.setCurrentIndex(0)

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #0d0f15;
                color: #e5e7eb;
                font-family: "Segoe UI", sans-serif;
            }
            QFrame#MergedSwitchBar {
                background: #181b25;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
            }
            QPushButton {
                background: #6366f1;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 7px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #7376f3;
            }
        """)

    def _copy_common_state(self, source, target):
        """Keep the visible crosshair settings consistent when changing UI."""
        common = [
            "size_val",
            "gap_val",
            "rotation_val",
            "opacity_val",
            "outline_val",
            "outline_thickness_val",
            "animation_mode",
            "animation_speed_val",
        ]
        for name in common:
            if hasattr(source, name) and hasattr(target, name):
                setattr(target, name, getattr(source, name))

        if hasattr(source, "color_val") and hasattr(target, "color_val"):
            target.color_val = QColor(source.color_val)

        # Share custom PNGs when both interfaces support them.
        if hasattr(source, "custom_pixmaps") and hasattr(target, "custom_pixmaps"):
            target.custom_pixmaps = dict(source.custom_pixmaps)

    def _sync_overlay(self, source, target):
        """Move the active overlay state to the interface being shown."""
        self._copy_common_state(source, target)

        active = bool(getattr(source, "overlay_active", False))

        # Hide the old overlay first so two crosshairs are never left running.
        if getattr(source, "overlay", None):
            source.overlay.hide()

        if active:
            target.overlay_active = True
            if getattr(target, "overlay", None) is None:
                target.overlay = target.__class__.__dict__.get(
                    "overlay", None
                )
            # Use the target's own toggle handler so its overlay class is correct.
            target.toggle_overlay(True)
        else:
            target.overlay_active = False
            if getattr(target, "overlay", None):
                target.overlay.hide()
            if hasattr(target, "toggle_btn"):
                target.toggle_btn.setChecked(False)

    def switch_ui(self, checked):
        index = 0 if checked else 1
        source = self.old_ui if index == 0 else self.new_ui
        target = self.new_ui if index == 0 else self.old_ui

        self._sync_overlay(source, target)
        self.interface_stack.setCurrentIndex(index)

        if checked:
            self.ui_switch.setText("Новый")
            self.ui_mode_label.setText("Интерфейс: Новый")
        else:
            self.ui_switch.setText("Классический")
            self.ui_mode_label.setText("Интерфейс: Классический")

    def closeEvent(self, event):
        for child in (self.new_ui, self.old_ui):
            try:
                child.close()
            except Exception:
                pass
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MergedSettingsWindow()
    win.show()
    sys.exit(app.exec_())
