"""
connect6 配置模块
常量与配置（棋盘大小、颜色、界面尺寸等）
"""

# 棋盘配置
BOARD_SIZE = 19
CELL_SIZE = 36
BOARD_MARGIN = 40
BOARD_PIXEL = CELL_SIZE * (BOARD_SIZE - 1)

# 窗口配置
SIDE_PANEL_WIDTH = 220
WINDOW_WIDTH = BOARD_MARGIN * 2 + BOARD_PIXEL + SIDE_PANEL_WIDTH + 30
WINDOW_HEIGHT = BOARD_MARGIN * 2 + BOARD_PIXEL + 60

# 颜色定义
COLOR_BG = (222, 184, 135)           # 棋盘背景（木色）
COLOR_BOARD = (222, 184, 135)
COLOR_LINE = (0, 0, 0)               # 棋盘线
COLOR_BLACK = (30, 30, 30)           # 黑子
COLOR_WHITE = (240, 240, 240)        # 白子
COLOR_HIGHLIGHT_BLACK = (0, 120, 255)  # 黑子高亮轮廓（蓝色）
COLOR_HIGHLIGHT_WHITE = (255, 50, 50)  # 白子高亮轮廓（红色）
COLOR_BUTTON = (100, 140, 200)
COLOR_BUTTON_HOVER = (130, 165, 220)
COLOR_BUTTON_TEXT = (255, 255, 255)
COLOR_TEXT = (50, 50, 50)
COLOR_TITLE = (40, 40, 40)
COLOR_PANEL_BG = (240, 235, 225)
COLOR_STAR = (0, 0, 0)              # 星位
COLOR_OVERLAY = (0, 0, 0, 128)      # 半透明覆盖

# 坐标标签颜色（A-S）
COLOR_LABEL = (0, 0, 0)

# 字体大小
FONT_SIZE_TITLE = 48
FONT_SIZE_SUBTITLE = 28
FONT_SIZE_BUTTON = 26
FONT_SIZE_TEXT = 20
FONT_SIZE_SMALL = 16
FONT_SIZE_WIN = 56

# 棋子半径
STONE_RADIUS = (CELL_SIZE // 2) - 2

# 星位（19x19标准星位）
STAR_POINTS = [
    (3, 3), (3, 9), (3, 15),
    (9, 3), (9, 9), (9, 15),
    (15, 3), (15, 9), (15, 15),
]

# AI 执黑时第一步星位选择权重
# 9个星位：天元(9,9)权重0.44，其余8个各0.07
AI_BLACK_FIRST_MOVE_WEIGHTS = {
    (3, 3): 0.07, (3, 9): 0.07, (3, 15): 0.07,
    (9, 3): 0.07, (9, 9): 0.44, (9, 15): 0.07,
    (15, 3): 0.07, (15, 9): 0.07, (15, 15): 0.07,
}


# 玩家常量
EMPTY = 0
BLACK = 1
WHITE = 2

import os
import sys


def _find_chinese_font() -> str | None:
    """跨平台查找可用的中文字体，返回路径或 None（回退默认字体）。"""
    # 1. 项目自带字体（优先，在 src 的上级目录 font/ 下）
    _base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(_base_dir, "font", "simhei.ttf"),
        os.path.join(_base_dir, "font", "SourceHanSansSC-Regular.ttf"),
    ]
    # 2. 系统级字体
    if sys.platform == "win32":
        candidates += [
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simsun.ttc",
        ]
    elif sys.platform == "darwin":
        candidates += [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
    else:  # Linux
        candidates += [
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        ]

    for path in candidates:
        if os.path.exists(path):
            return path
    return None


# 字体文件路径（跨平台自动检测，找不到则用默认字体）
FONT_PATH = _find_chinese_font()

# FPS
FPS = 30