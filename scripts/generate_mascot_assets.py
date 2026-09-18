"""Generate polished, custom 2D mascot artwork for NetPulse macOS menu bar.

Replaces placeholder frames with high-contrast, Retina-ready 44x44 PNG artwork:
- Cute chibi lion mascot with consistent design, palette, and proportions
- Crisp dark outlines for readability on dark and light macOS menu bars
- Rich layered shading, specular highlights, and expressive anime catchlights
- Perfect alignment and grounding across all animation states to prevent jitter:
  * idle (seated breathing, blink, and 4-frame yawn)
  * low (seated alert, tracking eyes, tail swish, ear perk)
  * walk (smooth 4-frame quadruped gait)
  * run (energetic 4-frame gallop with streaming mane and tail)
  * roar (4-frame crouch, puff, full roar with fangs, recover)
  * disconnected (peaceful sleeping pose with soft breathing and floating z)
  * reconnect (feline arch stretch and get-up sequence)
"""

from __future__ import annotations

import math
from pathlib import Path
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)

BASE_DIR = Path(__file__).resolve().parent.parent
MASCOT_DIR = BASE_DIR / "resources" / "mascot"

# ---------------------------------------------------------------------------
# Character Palette & Styling
# ---------------------------------------------------------------------------
# Outlines: Rich warm espresso outline for sharp contrast on light/dark macOS menu bar
C_OUTLINE = QColor("#361502")
C_OUTLINE_SOFT = QColor("#4A2007")

# Mane: Layered warm chocolate & cinnamon
C_MANE_BASE = QColor("#7D3308")
C_MANE_SHADE = QColor("#521F03")
C_MANE_HI = QColor("#A84E14")
C_MANE_TIP = QColor("#C4641D")

# Fur: Honey-gold duo-tone gradient
C_FUR_TOP = QColor("#FFCA45")
C_FUR_MID = QColor("#F5AB26")
C_FUR_SHADE = QColor("#D98208")

# Muzzle, Belly & Inner Ears: Warm vanilla cream
C_CREAM = QColor("#FFF4DC")
C_CREAM_SHADE = QColor("#EBD4A8")
C_INNER_EAR = QColor("#FFDCB8")

# Face & Features
C_EYE_DARK = QColor("#180A02")
C_WHITE = QColor("#FFFFFF")
C_NOSE = QColor("#301202")
C_BLUSH = QColor(255, 120, 110, 110)
C_MOUTH_DARK = QColor("#2E1002")
C_MOUTH_BG = QColor("#C93448")
C_TONGUE = QColor("#FF7A8E")
C_SLEEP_Z = QColor("#5B92E5")
C_SPARKLE = QColor("#FFD952")


def _init_frame() -> tuple[QImage, QPainter]:
    img = QImage(44, 44, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    return img, p


def _fur_brush(top_y: float, bot_y: float) -> QLinearGradient:
    grad = QLinearGradient(0, top_y, 0, bot_y)
    grad.setColorAt(0.0, C_FUR_TOP)
    grad.setColorAt(0.55, C_FUR_MID)
    grad.setColorAt(1.0, C_FUR_SHADE)
    return grad


def _mane_brush(cx: float, cy: float, radius: float) -> QRadialGradient:
    grad = QRadialGradient(cx - 2.0, cy - 2.0, radius)
    grad.setColorAt(0.0, C_MANE_HI)
    grad.setColorAt(0.65, C_MANE_BASE)
    grad.setColorAt(1.0, C_MANE_SHADE)
    return grad


# ---------------------------------------------------------------------------
# Reusable Mascot Anatomy Components
# ---------------------------------------------------------------------------

def _draw_tail(
    p: QPainter,
    base_x: float,
    base_y: float,
    ctrl_x: float,
    ctrl_y: float,
    tip_x: float,
    tip_y: float,
    tuft_angle: float = 0.0,
    tuft_scale: float = 1.0,
):
    """Draw smooth arched tail with outline and fluffy teardrop tuft."""
    # Tail stroke
    path = QPainterPath()
    path.moveTo(base_x, base_y)
    path.quadTo(ctrl_x, ctrl_y, tip_x, tip_y)

    # Outer outline
    p.setBrush(Qt.BrushStyle.NoBrush)
    pen_out = QPen(C_OUTLINE, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen_out)
    p.drawPath(path)

    # Inner fur stroke
    pen_in = QPen(C_FUR_MID, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen_in)
    p.drawPath(path)

    # Fluffy mane tuft at tip
    p.save()
    p.translate(tip_x, tip_y)
    p.rotate(tuft_angle)
    p.scale(tuft_scale, tuft_scale)

    tuft_path = QPainterPath()
    tuft_path.moveTo(0, 0)
    tuft_path.cubicTo(-2.5, -3.5, -4.0, -7.0, 0.0, -9.0)
    tuft_path.cubicTo(4.0, -7.0, 2.5, -3.5, 0, 0)

    p.setPen(QPen(C_OUTLINE, 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(QBrush(C_MANE_BASE))
    p.drawPath(tuft_path)

    # Tuft highlight streak
    p.setPen(QPen(C_MANE_HI, 1.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(0, -2.0), QPointF(0, -6.5))

    p.restore()


def _draw_mane(p: QPainter, cx: float, cy: float, radius: float = 11.0, flared: bool = False):
    """Draw lush, cloud-like mane with depth shadows and highlights."""
    num_petals = 10 if not flared else 12
    r_petal = 4.8 if not flared else 5.8
    dist = radius * 0.72

    # 1. Outer petals outline
    petals_path = QPainterPath()
    for i in range(num_petals):
        angle = 2 * math.pi * i / num_petals - 0.2
        px = cx + dist * math.cos(angle)
        py = cy + dist * math.sin(angle)
        petals_path.addEllipse(QPointF(px, py), r_petal, r_petal)
    petals_path.addEllipse(QPointF(cx, cy), radius, radius)

    p.setPen(QPen(C_OUTLINE, 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(_mane_brush(cx, cy, radius + r_petal))
    p.drawPath(petals_path)

    # 2. Interior fluff accents
    p.setPen(QPen(C_MANE_TIP, 1.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for i in range(0, num_petals, 2):
        angle = 2 * math.pi * i / num_petals - 0.2
        sx = cx + (dist - 1.5) * math.cos(angle)
        sy = cy + (dist - 1.5) * math.sin(angle)
        ex = cx + (dist + 2.0) * math.cos(angle)
        ey = cy + (dist + 2.0) * math.sin(angle)
        p.drawLine(QPointF(sx, sy), QPointF(ex, ey))


def _draw_ears(p: QPainter, cx: float, cy: float, twitch_left: bool = False, perk_right: bool = False):
    """Draw cute rounded lion ears with creamy inner ear pads."""
    # Left Ear (back/side)
    lx = cx - 6.5
    ly = cy - 7.5 + (-1.0 if twitch_left else 0.0)
    p.setPen(QPen(C_OUTLINE, 1.2))
    p.setBrush(QBrush(C_FUR_MID))
    p.drawEllipse(QPointF(lx, ly), 3.4, 3.4)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(C_INNER_EAR))
    p.drawEllipse(QPointF(lx + 0.3, ly + 0.3), 2.0, 2.0)

    # Right Ear (front/side)
    rx = cx + 4.5
    ry = cy - 8.0 + (-1.0 if perk_right else 0.0)
    p.setPen(QPen(C_OUTLINE, 1.2))
    p.setBrush(QBrush(C_FUR_TOP))
    p.drawEllipse(QPointF(rx, ry), 3.4, 3.4)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(C_INNER_EAR))
    p.drawEllipse(QPointF(rx - 0.2, ry + 0.2), 2.0, 2.0)


def _draw_head_and_face(
    p: QPainter,
    cx: float,
    cy: float,
    look_dx: float = 0.0,
    look_dy: float = 0.0,
    eye_mode: str = "open",
    mouth_mode: str = "smile",
    twitch_ear: bool = False,
):
    """Draw chibi lion head, muzzle, nose, cute blush, eyes, and mouth."""
    _draw_ears(p, cx, cy, twitch_left=twitch_ear)

    # Head base
    head_rect = QRectF(cx - 7.5, cy - 7.0, 15.0, 14.5)
    p.setPen(QPen(C_OUTLINE, 1.3))
    p.setBrush(_fur_brush(cy - 7.0, cy + 7.5))
    p.drawEllipse(head_rect)

    # Soft cream muzzle / cheeks puff
    snout_cx = cx + 3.0 + look_dx
    snout_cy = cy + 2.4 + look_dy
    p.setPen(QPen(C_OUTLINE_SOFT, 1.0))
    p.setBrush(QBrush(C_CREAM))
    p.drawEllipse(QPointF(snout_cx - 1.8, snout_cy), 3.4, 2.8)
    p.drawEllipse(QPointF(snout_cx + 1.8, snout_cy), 3.4, 2.8)

    # Cheerful cheek blush
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(C_BLUSH))
    p.drawEllipse(QPointF(cx - 4.5, cy + 2.8), 2.0, 1.3)
    p.drawEllipse(QPointF(cx + 6.0, cy + 2.8), 2.0, 1.3)

    # Nose
    nose_x = snout_cx
    nose_y = snout_cy - 1.8
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(C_NOSE))
    p.drawPolygon([
        QPointF(nose_x - 1.6, nose_y),
        QPointF(nose_x + 1.6, nose_y),
        QPointF(nose_x, nose_y + 1.5),
    ])
    # Specular catchlight on nose
    p.setBrush(QBrush(C_WHITE))
    p.drawEllipse(QPointF(nose_x - 0.5, nose_y + 0.3), 0.5, 0.4)

    # Eyes
    eye_x = cx + 2.2 + look_dx
    eye_y = cy - 0.8 + look_dy
    _draw_eye(p, eye_x, eye_y, mode=eye_mode)

    # Mouth
    _draw_mouth(p, snout_cx, snout_cy, mode=mouth_mode)


def _draw_eye(p: QPainter, x: float, y: float, mode: str = "open"):
    """Draw sparkling anime mascot eyes with double specular catchlights."""
    if mode == "open":
        # Eye base
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(C_EYE_DARK))
        p.drawEllipse(QPointF(x, y), 2.0, 2.6)

        # Primary specular highlight
        p.setBrush(QBrush(C_WHITE))
        p.drawEllipse(QPointF(x + 0.6, y - 0.9), 1.0, 1.0)
        # Secondary tiny sparkle
        p.drawEllipse(QPointF(x - 0.8, y + 1.0), 0.55, 0.55)

    elif mode == "blink" or mode == "happy":
        # Happy curved eye arc: ^
        pen = QPen(C_OUTLINE, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(x - 2.0, y + 0.6)
        path.quadTo(x, y - 1.8, x + 2.0, y + 0.6)
        p.drawPath(path)

    elif mode == "sleep":
        # Relaxed sleeping eye: -
        pen = QPen(C_OUTLINE, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(x - 1.8, y + 0.4)
        path.quadTo(x, y + 1.1, x + 1.8, y + 0.4)
        p.drawPath(path)

    elif mode == "roar":
        # Intense determined roaring eye
        pen = QPen(C_OUTLINE, 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(x - 2.2, y + 1.2)
        path.quadTo(x, y - 1.6, x + 2.2, y + 0.4)
        p.drawPath(path)


def _draw_mouth(p: QPainter, cx: float, cy: float, mode: str = "smile"):
    """Draw mouth variations: smile, small open, wide yawn, full roar."""
    if mode == "smile":
        pen = QPen(C_OUTLINE, 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        # Cat-like mouth curve
        p.drawLine(QPointF(cx, cy - 0.3), QPointF(cx, cy + 0.8))
        path = QPainterPath()
        path.moveTo(cx - 1.6, cy + 0.8)
        path.quadTo(cx - 0.8, cy + 1.6, cx, cy + 0.8)
        path.quadTo(cx + 0.8, cy + 1.6, cx + 1.6, cy + 0.8)
        p.drawPath(path)

    elif mode == "yawn_small":
        p.setPen(QPen(C_OUTLINE, 1.1))
        p.setBrush(QBrush(C_MOUTH_BG))
        p.drawEllipse(QPointF(cx + 0.2, cy + 1.6), 1.8, 2.2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(C_TONGUE))
        p.drawEllipse(QPointF(cx + 0.2, cy + 2.4), 1.2, 1.0)

    elif mode == "yawn_wide":
        p.setPen(QPen(C_OUTLINE, 1.2))
        p.setBrush(QBrush(C_MOUTH_BG))
        p.drawEllipse(QPointF(cx + 0.5, cy + 2.0), 3.2, 4.2)
        # Pink tongue
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(C_TONGUE))
        p.drawEllipse(QPointF(cx + 0.5, cy + 3.6), 2.2, 1.8)
        # Tiny cute fangs
        p.setBrush(QBrush(C_WHITE))
        p.drawPolygon([QPointF(cx - 1.2, cy - 0.1), QPointF(cx - 0.4, cy - 0.1), QPointF(cx - 0.8, cy + 1.0)])
        p.drawPolygon([QPointF(cx + 1.4, cy - 0.1), QPointF(cx + 2.2, cy - 0.1), QPointF(cx + 1.8, cy + 1.0)])

    elif mode == "roar_open":
        # Fierce open roaring jaw
        mouth_path = QPainterPath()
        mouth_path.moveTo(cx - 1.8, cy)
        mouth_path.cubicTo(cx - 1.0, cy - 1.5, cx + 4.5, cy - 0.5, cx + 4.0, cy + 2.5)
        mouth_path.cubicTo(cx + 3.0, cy + 5.5, cx - 1.0, cy + 4.5, cx - 1.8, cy)

        p.setPen(QPen(C_OUTLINE, 1.3))
        p.setBrush(QBrush(C_MOUTH_BG))
        p.drawPath(mouth_path)

        # Tongue
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(C_TONGUE))
        p.drawEllipse(QPointF(cx + 1.2, cy + 3.2), 2.6, 2.0)

        # Top fangs
        p.setBrush(QBrush(C_WHITE))
        p.drawPolygon([QPointF(cx - 0.8, cy - 0.2), QPointF(cx + 0.2, cy - 0.2), QPointF(cx - 0.3, cy + 1.2)])
        p.drawPolygon([QPointF(cx + 2.2, cy + 0.2), QPointF(cx + 3.2, cy + 0.2), QPointF(cx + 2.7, cy + 1.5)])
        # Bottom fangs
        p.drawPolygon([QPointF(cx + 0.2, cy + 4.2), QPointF(cx + 1.0, cy + 4.2), QPointF(cx + 0.6, cy + 3.0)])


def _draw_paws_toes(p: QPainter, x: float, y: float, w: float, h: float):
    """Draw paw with clean outline and cute toe separator lines."""
    rect = QRectF(x, y, w, h)
    p.setPen(QPen(C_OUTLINE, 1.2))
    p.setBrush(QBrush(C_CREAM))
    p.drawRoundedRect(rect, 2.2, 2.2)

    # Toe slits
    p.setPen(QPen(C_OUTLINE, 1.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(x + w * 0.36, y + h * 0.55), QPointF(x + w * 0.36, y + h))
    p.drawLine(QPointF(x + w * 0.68, y + h * 0.55), QPointF(x + w * 0.68, y + h))


# ---------------------------------------------------------------------------
# State Renderers
# ---------------------------------------------------------------------------

def generate_idle_frames(out_dir: Path):
    """Generate seated idle frames with breathing, blink, and infrequent yawn."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # 4-frame normal idle loop:
    # Frame 0: Baseline seated breathing
    # Frame 1: Inhale, gentle chest lift (+0.8px)
    # Frame 2: Cute happy blink
    # Frame 3: Exhale, settling
    breathes = [0.0, 0.8, 0.4, 0.1]
    eyes = ["open", "open", "blink", "open"]

    for i in range(4):
        img, p = _init_frame()
        dy = breathes[i]
        eye = eyes[i]

        # Tail: gentle curl behind haunch
        _draw_tail(
            p,
            base_x=12.0, base_y=32.0,
            ctrl_x=5.5, ctrl_y=30.0,
            tip_x=6.5, tip_y=20.0 + dy * 1.5,
            tuft_angle=-25.0,
        )

        # Seated body: Hind leg haunch
        p.setPen(QPen(C_OUTLINE, 1.3))
        p.setBrush(_fur_brush(24, 36))
        p.drawEllipse(QRectF(10.5, 26.5, 9.0, 9.5))

        # Main torso
        p.drawRoundedRect(QRectF(13.0, 19.5 - dy, 13.5, 14.5 + dy), 6.0, 6.0)

        # Cream chest bib
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(C_CREAM))
        p.drawEllipse(QRectF(17.5, 21.0 - dy, 6.5, 9.0))

        # Front paws planted firmly on baseline y=36
        _draw_paws_toes(p, 17.5, 28.5, 4.4, 7.5)
        _draw_paws_toes(p, 22.5, 28.5, 4.4, 7.5)

        # Mane & Head
        head_cx = 23.0
        head_cy = 16.5 - dy
        _draw_mane(p, head_cx, head_cy, radius=11.0)
        _draw_head_and_face(p, head_cx, head_cy, eye_mode=eye, mouth_mode="smile")

        p.end()
        img.save(str(out_dir / f"frame_{i}.png"))

    # 4-frame yawn sequence:
    yawn_modes = ["yawn_small", "yawn_wide", "yawn_wide", "smile"]
    yawn_eyes = ["happy", "happy", "happy", "blink"]
    yawn_lifts = [0.2, 0.8, 0.5, 0.0]

    for i in range(4):
        img, p = _init_frame()
        dy = yawn_lifts[i]
        mouth = yawn_modes[i]
        eye = yawn_eyes[i]

        _draw_tail(
            p,
            base_x=12.0, base_y=32.0,
            ctrl_x=5.0, ctrl_y=30.0,
            tip_x=7.0, tip_y=22.0,
            tuft_angle=-20.0,
        )

        p.setPen(QPen(C_OUTLINE, 1.3))
        p.setBrush(_fur_brush(24, 36))
        p.drawEllipse(QRectF(10.5, 26.5, 9.0, 9.5))
        p.drawRoundedRect(QRectF(13.0, 19.5 - dy, 13.5, 14.5 + dy), 6.0, 6.0)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(C_CREAM))
        p.drawEllipse(QRectF(17.5, 21.0 - dy, 6.5, 9.0))

        _draw_paws_toes(p, 17.5, 28.5, 4.4, 7.5)
        _draw_paws_toes(p, 22.5, 28.5, 4.4, 7.5)

        head_cx = 23.0
        head_cy = 16.5 - dy
        _draw_mane(p, head_cx, head_cy, radius=11.2)
        _draw_head_and_face(p, head_cx, head_cy, eye_mode=eye, mouth_mode=mouth)

        p.end()
        img.save(str(out_dir / f"yawn_{i}.png"))


def generate_low_frames(out_dir: Path):
    """Generate seated alert frames with active tail swish and ear perk."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tail_configs = [
        (5.0, 21.0, -35.0),
        (3.5, 24.0, -15.0),
        (5.5, 18.0, -45.0),
        (4.0, 22.0, -25.0),
    ]

    for i in range(4):
        img, p = _init_frame()
        tip_x, tip_y, tuft_rot = tail_configs[i]
        twitch = (i == 3)

        _draw_tail(
            p,
            base_x=12.0, base_y=32.0,
            ctrl_x=4.0, ctrl_y=28.0,
            tip_x=tip_x, tip_y=tip_y,
            tuft_angle=tuft_rot,
        )

        p.setPen(QPen(C_OUTLINE, 1.3))
        p.setBrush(_fur_brush(24, 36))
        p.drawEllipse(QRectF(10.5, 26.5, 9.0, 9.5))
        p.drawRoundedRect(QRectF(13.0, 19.5, 13.5, 14.5), 6.0, 6.0)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(C_CREAM))
        p.drawEllipse(QRectF(17.5, 21.0, 6.5, 9.0))

        _draw_paws_toes(p, 17.5, 28.5, 4.4, 7.5)
        _draw_paws_toes(p, 22.5, 28.5, 4.4, 7.5)

        head_cx = 23.0
        head_cy = 16.5
        _draw_mane(p, head_cx, head_cy, radius=11.0)
        _draw_head_and_face(
            p, head_cx, head_cy,
            look_dx=0.8, eye_mode="open", mouth_mode="smile",
            twitch_ear=twitch,
        )

        p.end()
        img.save(str(out_dir / f"frame_{i}.png"))


def generate_walk_frames(out_dir: Path):
    """Generate natural quadruped walking cycle with alternating limb gait."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # 4-frame walking gait parameters:
    # (bl_x, bl_y, fl_x, fl_y, br_x, br_y, fr_x, fr_y, bob_y, tail_tip_y)
    walk_steps = [
        # Frame 0: FL reaching forward, BR driving back
        (10.0, 28.5, 25.0, 29.0, 15.0, 29.5, 20.0, 28.0, 0.0, 19.0),
        # Frame 1: Passing pose 1 (limbs pass under, torso raises +0.6)
        (12.0, 29.0, 23.0, 27.5, 13.0, 28.5, 21.5, 29.0, -0.6, 21.0),
        # Frame 2: FR reaching forward, BL driving back
        (15.0, 29.5, 20.5, 28.0, 10.0, 28.5, 25.5, 29.0, 0.0, 19.0),
        # Frame 3: Passing pose 2
        (13.0, 28.5, 22.0, 29.0, 12.0, 29.0, 23.5, 27.5, -0.6, 21.0),
    ]

    for i in range(4):
        img, p = _init_frame()
        bl_x, bl_y, fl_x, fl_y, br_x, br_y, fr_x, fr_y, dy, tail_y = walk_steps[i]

        # Tail swishing in rhythm
        _draw_tail(
            p,
            base_x=10.0, base_y=26.0 + dy,
            ctrl_x=3.0, ctrl_y=25.0,
            tip_x=4.0, tip_y=tail_y,
            tuft_angle=-20.0 if i % 2 == 0 else -35.0,
        )

        # Background legs (darker shade for depth)
        p.setPen(QPen(C_OUTLINE, 1.2))
        p.setBrush(QBrush(C_FUR_SHADE))
        p.drawRoundedRect(QRectF(bl_x, bl_y + dy, 3.8, 7.5), 1.8, 1.8)
        p.drawRoundedRect(QRectF(fl_x, fl_y + dy, 3.8, 7.5), 1.8, 1.8)

        # Torso
        p.setBrush(_fur_brush(19 + dy, 31 + dy))
        p.drawRoundedRect(QRectF(9.5, 19.5 + dy, 16.5, 11.0), 5.5, 5.5)

        # Cream belly patch
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(C_CREAM))
        p.drawEllipse(QRectF(14.0, 23.5 + dy, 8.5, 5.5))

        # Foreground legs
        _draw_paws_toes(p, br_x, br_y + dy, 4.0, 7.5)
        _draw_paws_toes(p, fr_x, fr_y + dy, 4.0, 7.5)

        # Mane & Head
        head_cx = 24.5
        head_cy = 16.5 + dy
        _draw_mane(p, head_cx, head_cy, radius=10.8)
        _draw_head_and_face(p, head_cx, head_cy, look_dx=0.8, eye_mode="open", mouth_mode="smile")

        p.end()
        img.save(str(out_dir / f"frame_{i}.png"))


def generate_run_frames(out_dir: Path):
    """Generate dynamic running gallop with wind-blown streaming mane and tail."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # 4-frame gallop cycle:
    # Frame 0: Full extension (airborne leap, front paws forward, hind legs swept back)
    # Frame 1: Landing impact (front paws plant, body compresses)
    # Frame 2: Coiled gather (all paws tucked under arched body, airborne)
    # Frame 3: Launch push-off (hind legs drive down, chest launches up)
    run_configs = [
        # (f_reach, b_reach, body_y, tail_tip_y, mane_flare)
        (28.5, 6.0, 19.0, 17.0, True),
        (26.0, 8.5, 21.5, 19.0, False),
        (20.5, 14.5, 18.0, 15.0, False),
        (25.5, 7.0, 19.5, 17.5, True),
    ]

    for i in range(4):
        img, p = _init_frame()
        f_reach, b_reach, b_y, tail_y, flare = run_configs[i]

        # Streaming horizontal tail
        _draw_tail(
            p,
            base_x=8.5, base_y=b_y + 4.5,
            ctrl_x=2.0, ctrl_y=b_y + 3.0,
            tip_x=1.5, tip_y=tail_y,
            tuft_angle=-75.0,
            tuft_scale=1.1,
        )

        # Background running limbs
        p.setPen(QPen(C_OUTLINE, 1.2))
        p.setBrush(QBrush(C_FUR_SHADE))
        p.drawRoundedRect(QRectF(b_reach - 1.2, b_y + 5.0, 4.0, 8.0), 1.8, 1.8)
        p.drawRoundedRect(QRectF(f_reach - 1.2, b_y + 5.0, 4.0, 8.0), 1.8, 1.8)

        # Stretched elongated torso
        p.setBrush(_fur_brush(b_y, b_y + 11.5))
        p.drawRoundedRect(QRectF(8.0, b_y, 18.5, 10.5), 5.0, 5.0)

        # Foreground running limbs
        _draw_paws_toes(p, b_reach + 1.2, b_y + 5.5, 4.2, 8.0)
        _draw_paws_toes(p, f_reach + 1.2, b_y + 5.5, 4.2, 8.0)

        # Wind-blown flared mane & forward head
        head_cx = 25.5
        head_cy = b_y - 3.0
        _draw_mane(p, head_cx, head_cy, radius=11.5, flared=flare)
        _draw_head_and_face(
            p, head_cx, head_cy,
            look_dx=1.4, eye_mode="open", mouth_mode="smile",
        )

        p.end()
        img.save(str(out_dir / f"frame_{i}.png"))


def generate_roar_frames(out_dir: Path):
    """Generate majestic roar sequence: crouch, wind-up, full roar with fangs, recover."""
    out_dir.mkdir(parents=True, exist_ok=True)

    for i in range(4):
        img, p = _init_frame()

        if i == 0:  # Crouch / windup
            _draw_tail(
                p, base_x=10.0, base_y=30.0, ctrl_x=4.0, ctrl_y=28.0,
                tip_x=5.0, tip_y=22.0, tuft_angle=-25.0,
            )
            p.setPen(QPen(C_OUTLINE, 1.3))
            p.setBrush(_fur_brush(21, 33))
            p.drawRoundedRect(QRectF(9.5, 21.0, 16.5, 11.5), 5.5, 5.5)
            _draw_paws_toes(p, 12.0, 27.5, 4.4, 7.5)
            _draw_paws_toes(p, 21.5, 27.5, 4.4, 7.5)

            _draw_mane(p, cx=24.0, cy=18.5, radius=11.0)
            _draw_head_and_face(p, cx=24.0, cy=18.5, look_dx=0.5, eye_mode="open", mouth_mode="smile")

        elif i == 1:  # Chest puffed, jaw opening
            _draw_tail(
                p, base_x=9.0, base_y=28.0, ctrl_x=3.0, ctrl_y=24.0,
                tip_x=3.5, tip_y=18.0, tuft_angle=-40.0,
            )
            p.setPen(QPen(C_OUTLINE, 1.3))
            p.setBrush(_fur_brush(18, 31))
            p.drawRoundedRect(QRectF(9.0, 18.5, 17.0, 12.5), 6.0, 6.0)
            _draw_paws_toes(p, 11.5, 26.5, 4.4, 8.0)
            _draw_paws_toes(p, 22.0, 26.5, 4.4, 8.0)

            _draw_mane(p, cx=24.5, cy=15.5, radius=11.8, flared=True)
            _draw_head_and_face(p, cx=24.5, cy=15.5, look_dx=1.0, eye_mode="open", mouth_mode="yawn_small")

        elif i == 2:  # FULL MAJESTIC ROAR!
            _draw_tail(
                p, base_x=8.5, base_y=27.0, ctrl_x=1.5, ctrl_y=20.0,
                tip_x=1.5, tip_y=14.0, tuft_angle=-60.0, tuft_scale=1.2,
            )
            p.setPen(QPen(C_OUTLINE, 1.3))
            p.setBrush(_fur_brush(17, 31))
            p.drawRoundedRect(QRectF(8.5, 17.5, 18.0, 13.5), 6.0, 6.0)
            _draw_paws_toes(p, 11.0, 26.0, 4.6, 8.5)
            _draw_paws_toes(p, 22.5, 26.0, 4.6, 8.5)

            # Flared magnificent mane with fiery tufts
            _draw_mane(p, cx=25.0, cy=14.0, radius=12.5, flared=True)
            _draw_head_and_face(p, cx=25.0, cy=14.0, look_dx=1.5, eye_mode="roar", mouth_mode="roar_open")

            # Roar energy sparkles / sound rays
            p.setPen(QPen(C_SPARKLE, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(38.0, 11.0), QPointF(42.5, 9.0))
            p.drawLine(QPointF(39.0, 15.0), QPointF(43.5, 15.0))
            p.drawLine(QPointF(38.0, 19.0), QPointF(42.5, 21.0))

        elif i == 3:  # Proud recover with smile
            _draw_tail(
                p, base_x=10.0, base_y=29.0, ctrl_x=3.5, ctrl_y=26.0,
                tip_x=4.5, tip_y=20.0, tuft_angle=-30.0,
            )
            p.setPen(QPen(C_OUTLINE, 1.3))
            p.setBrush(_fur_brush(19, 32))
            p.drawRoundedRect(QRectF(9.5, 19.0, 17.0, 12.0), 5.5, 5.5)
            _draw_paws_toes(p, 12.0, 27.0, 4.4, 8.0)
            _draw_paws_toes(p, 22.0, 27.0, 4.4, 8.0)

            _draw_mane(p, cx=24.5, cy=16.0, radius=11.2)
            _draw_head_and_face(p, cx=24.5, cy=16.0, look_dx=0.8, eye_mode="happy", mouth_mode="smile")

        p.end()
        img.save(str(out_dir / f"frame_{i}.png"))


def generate_disconnected_frames(out_dir: Path):
    """Generate peaceful sleeping/resting pose with soft breath and floating z."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # 4 frames: soft chest breathing and floating dreamy Zzz
    z_configs = [
        None,
        (33.0, 14.0, 0.8),
        (35.5, 10.0, 1.1),
        (37.0, 7.0, 0.9),
    ]

    for i in range(4):
        img, p = _init_frame()
        dy = 0.6 if i in (1, 2) else 0.0

        # Tail tucked flat beside paws
        _draw_tail(
            p,
            base_x=8.5, base_y=33.5,
            ctrl_x=3.5, ctrl_y=34.0,
            tip_x=3.0, tip_y=32.0,
            tuft_angle=85.0,
        )

        # Curled horizontal body
        p.setPen(QPen(C_OUTLINE, 1.3))
        p.setBrush(_fur_brush(25 - dy, 35.5))
        p.drawRoundedRect(QRectF(8.0, 25.0 - dy, 22.5, 10.5 + dy), 5.5, 5.5)

        # Front paws stretched forward resting head
        _draw_paws_toes(p, 22.0, 31.0, 7.5, 4.5)

        # Mane resting low
        head_cx = 23.5
        head_cy = 23.5 - dy
        _draw_mane(p, head_cx, head_cy, radius=9.8)
        _draw_head_and_face(
            p, head_cx, head_cy,
            look_dx=0.0, eye_mode="sleep", mouth_mode="smile",
        )

        # Floating sleepy Z
        z_info = z_configs[i]
        if z_info:
            zx, zy, z_scale = z_info
            pen = QPen(C_SLEEP_Z, 1.4 * z_scale, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            w = 3.6 * z_scale
            h = 4.0 * z_scale
            z_path = QPainterPath()
            z_path.moveTo(zx, zy)
            z_path.lineTo(zx + w, zy)
            z_path.lineTo(zx, zy + h)
            z_path.lineTo(zx + w, zy + h)
            p.drawPath(z_path)

        p.end()
        img.save(str(out_dir / f"frame_{i}.png"))


def generate_reconnect_frames(out_dir: Path):
    """Generate wake-up and stretch sequence: head pops up, feline arch stretch, ready stance."""
    out_dir.mkdir(parents=True, exist_ok=True)

    for i in range(4):
        img, p = _init_frame()

        if i == 0:  # Head pops up from paws, eyes wide awake
            _draw_tail(
                p, base_x=8.5, base_y=33.0, ctrl_x=3.0, ctrl_y=32.0,
                tip_x=4.0, tip_y=28.0, tuft_angle=30.0,
            )
            p.setPen(QPen(C_OUTLINE, 1.3))
            p.setBrush(_fur_brush(24, 35))
            p.drawRoundedRect(QRectF(8.0, 24.5, 22.0, 11.0), 5.5, 5.5)
            _draw_paws_toes(p, 22.0, 31.0, 7.5, 4.5)

            head_cx = 23.5
            head_cy = 19.5
            _draw_mane(p, head_cx, head_cy, radius=10.2)
            _draw_head_and_face(p, head_cx, head_cy, eye_mode="open", mouth_mode="smile")

        elif i == 1:  # Feline arch stretch: front paws stretched far forward, hind up
            _draw_tail(
                p, base_x=8.0, base_y=28.0, ctrl_x=2.0, ctrl_y=22.0,
                tip_x=2.5, tip_y=16.0, tuft_angle=-65.0,
            )
            p.setPen(QPen(C_OUTLINE, 1.3))
            p.setBrush(_fur_brush(21, 35))
            p.drawRoundedRect(QRectF(8.5, 21.0, 18.0, 11.0), 5.0, 5.0)

            # Hind paws standing
            _draw_paws_toes(p, 8.5, 27.5, 4.4, 8.0)
            # Front paws stretched way out
            _draw_paws_toes(p, 25.0, 30.5, 8.5, 4.5)

            # Head lowered in stretch
            head_cx = 22.5
            head_cy = 20.0
            _draw_mane(p, head_cx, head_cy, radius=10.5)
            _draw_head_and_face(p, head_cx, head_cy, look_dx=0.5, eye_mode="happy", mouth_mode="smile")

        elif i == 2:  # Standing up on all 4 legs, shaking out mane
            _draw_tail(
                p, base_x=10.0, base_y=27.0, ctrl_x=4.0, ctrl_y=24.0,
                tip_x=5.0, tip_y=18.0, tuft_angle=-35.0,
            )
            p.setPen(QPen(C_OUTLINE, 1.3))
            p.setBrush(_fur_brush(19, 32))
            p.drawRoundedRect(QRectF(9.5, 19.5, 16.5, 11.5), 5.5, 5.5)
            _draw_paws_toes(p, 11.5, 27.5, 4.4, 8.0)
            _draw_paws_toes(p, 22.0, 27.5, 4.4, 8.0)

            head_cx = 23.5
            head_cy = 16.5
            _draw_mane(p, head_cx, head_cy, radius=11.2)
            _draw_head_and_face(p, head_cx, head_cy, eye_mode="happy", mouth_mode="smile")

        elif i == 3:  # Ready stance, confident smile forward
            _draw_tail(
                p, base_x=10.5, base_y=26.5, ctrl_x=4.5, ctrl_y=22.0,
                tip_x=6.0, tip_y=17.0, tuft_angle=-25.0,
            )
            p.setPen(QPen(C_OUTLINE, 1.3))
            p.setBrush(_fur_brush(19, 32))
            p.drawRoundedRect(QRectF(9.5, 19.0, 16.5, 11.5), 5.5, 5.5)
            _draw_paws_toes(p, 12.0, 27.0, 4.4, 8.0)
            _draw_paws_toes(p, 22.5, 27.0, 4.4, 8.0)

            head_cx = 24.5
            head_cy = 16.0
            _draw_mane(p, head_cx, head_cy, radius=11.0)
            _draw_head_and_face(p, head_cx, head_cy, look_dx=0.8, eye_mode="open", mouth_mode="smile")

        p.end()
        img.save(str(out_dir / f"frame_{i}.png"))


def main():
    print(f"Generating polished mascot artwork in {MASCOT_DIR}...")
    generate_idle_frames(MASCOT_DIR / "idle")
    generate_low_frames(MASCOT_DIR / "low")
    generate_walk_frames(MASCOT_DIR / "walk")
    generate_run_frames(MASCOT_DIR / "run")
    generate_roar_frames(MASCOT_DIR / "roar")
    generate_disconnected_frames(MASCOT_DIR / "disconnected")
    generate_reconnect_frames(MASCOT_DIR / "reconnect")
    print("Polished mascot artwork generated successfully!")


if __name__ == "__main__":
    main()
