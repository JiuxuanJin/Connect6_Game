"""
connect6 图形界面模块
Pygame 实现，包含主菜单、规则介绍、对局界面、获胜界面
"""

from __future__ import annotations
import sys
import pygame
from .config import (
    BOARD_SIZE, CELL_SIZE, BOARD_MARGIN, BOARD_PIXEL,
    SIDE_PANEL_WIDTH, WINDOW_WIDTH, WINDOW_HEIGHT,
    COLOR_BG, COLOR_BOARD, COLOR_LINE, COLOR_BLACK, COLOR_WHITE,
    COLOR_HIGHLIGHT_BLACK, COLOR_HIGHLIGHT_WHITE,
    COLOR_BUTTON, COLOR_BUTTON_HOVER, COLOR_BUTTON_TEXT,
    COLOR_TEXT, COLOR_TITLE, COLOR_PANEL_BG, COLOR_STAR,
    COLOR_OVERLAY, COLOR_LABEL,
    FONT_SIZE_TITLE, FONT_SIZE_SUBTITLE, FONT_SIZE_BUTTON,
    FONT_SIZE_TEXT, FONT_SIZE_SMALL, FONT_SIZE_WIN,
    STONE_RADIUS, STAR_POINTS, EMPTY, BLACK, WHITE, FPS, FONT_PATH,
)
from .board import Board
from .game_controller import GameController


class Button:
    """通用按钮"""

    def __init__(self, x: int, y: int, w: int, h: int, text: str,
                 font_size: int = FONT_SIZE_BUTTON,
                 color: tuple = COLOR_BUTTON,
                 hover_color: tuple = COLOR_BUTTON_HOVER,
                 text_color: tuple = COLOR_BUTTON_TEXT):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.font_size = font_size
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self._hovered = False
        self._font = None

    def set_font(self, font: pygame.font.Font):
        self._font = font

    def draw(self, screen: pygame.Surface, font: pygame.font.Font):
        mouse_pos = pygame.mouse.get_pos()
        self._hovered = self.rect.collidepoint(mouse_pos)
        bg = self.hover_color if self._hovered else self.color
        pygame.draw.rect(screen, bg, self.rect, border_radius=8)
        pygame.draw.rect(screen, (0, 0, 0), self.rect, width=2, border_radius=8)
        text_surf = font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def is_clicked(self, pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)


class GUI:
    """图形界面主类"""

    def __init__(self, use_ai: bool = False, ai_player_color: int = WHITE,
                 ai_search_depth: int = 1, ai_enable_force_win: bool = False,
                 ai_ad_v: float = 1.0):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("六子棋 - Connect6")
        self.clock = pygame.time.Clock()
        self.running = True

        # 模式选择状态
        self._mode_selection_active = False
        self._use_ai = use_ai
        self._ai_player_color = ai_player_color
        self._ai_search_depth = ai_search_depth
        self._ai_enable_force_win = ai_enable_force_win
        self._ai_ad_v = ai_ad_v
        self._ai_enable_multi_threat = False
        self._mode_buttons: list[Button] = []
        self._mode_color_buttons: list[Button] = []
        self._mode_difficulty_buttons: list[Button] = []
        self._mode_difficulty_texts: dict[str, int] = {}

        # 字体加载（带中文字体回退）
        if FONT_PATH is not None:
            self.font_title = pygame.font.Font(FONT_PATH, FONT_SIZE_TITLE)
            self.font_subtitle = pygame.font.Font(FONT_PATH, FONT_SIZE_SUBTITLE)
            self.font_button = pygame.font.Font(FONT_PATH, FONT_SIZE_BUTTON)
            self.font_text = pygame.font.Font(FONT_PATH, FONT_SIZE_TEXT)
            self.font_small = pygame.font.Font(FONT_PATH, FONT_SIZE_SMALL)
            self.font_win = pygame.font.Font(FONT_PATH, FONT_SIZE_WIN)
        else:
            # 回退：尝试系统字体（指定中文名让 SysFont 匹配）
            chinese_fonts = [
                "SimHei", "Microsoft YaHei", "SimSun", "PingFang SC",
                "Noto Sans CJK SC", "WenQuanYi Zen Hei", "sans-serif",
            ]
            sys_font = None
            for name in chinese_fonts:
                try:
                    test_font = pygame.font.SysFont(name, 24)
                    # 验证能否渲染中文
                    test_surf = test_font.render("中文测试", True, (255, 255, 255))
                    if test_surf.get_width() > 20:
                        sys_font = name
                        break
                except Exception:
                    continue
            if sys_font is None:
                sys_font = None  # 使用 pygame 默认字体（可能无中文）

            self.font_title = pygame.font.Font(
                pygame.font.match_font(sys_font) if sys_font else None,
                FONT_SIZE_TITLE,
            )
            self.font_subtitle = pygame.font.Font(
                pygame.font.match_font(sys_font) if sys_font else None,
                FONT_SIZE_SUBTITLE,
            )
            self.font_button = pygame.font.Font(
                pygame.font.match_font(sys_font) if sys_font else None,
                FONT_SIZE_BUTTON,
            )
            self.font_text = pygame.font.Font(
                pygame.font.match_font(sys_font) if sys_font else None,
                FONT_SIZE_TEXT,
            )
            self.font_small = pygame.font.Font(
                pygame.font.match_font(sys_font) if sys_font else None,
                FONT_SIZE_SMALL,
            )
            self.font_win = pygame.font.Font(
                pygame.font.match_font(sys_font) if sys_font else None,
                FONT_SIZE_WIN,
            )

        # 当前状态
        self.state = "menu"  # menu, game, rules, win, mode_select
        self.prev_state = None  # 用于 ESC 处理

        # 游戏模式（可修改）
        self.use_ai = use_ai  # True=人机对战, False=双人对战
        self._mode_ai_selected = use_ai  # 模式选择界面中的勾选状态

        # 对局控制器（延迟到确认模式后创建）
        self.controller: GameController | None = None
        self._init_controller()

        # 主菜单按钮
        self._init_menu_buttons()

        # 对局界面按钮
        self._init_game_buttons()

        # 规则介绍返回按钮
        self._init_rules_buttons()

        # 确认对话框按钮
        self._init_dialog_buttons()

        # 规则的文本行
        self.rules_text_lines = [
            "六子棋 - 游戏介绍",
            "",
            "棋盘：19×19",
            "规则：黑先白后，黑方第一手落1子，之后双方轮流落2子，横、竖、对角线连成6子获胜",
            "",
            "操作说明：",
            "· 鼠标点击空位落子",
            "· 新落白子红色高亮，新落黑子蓝色高亮",
            "· 悔棋恢复上次落子前状态",
            "· 每轮最多悔棋1次，悔棋后2次行动内不可再悔棋",
            "· 前2次落子不能悔棋", 
            "",
            "模式选择说明：",
            "· 模式选择界面可以切换双人/人机对战，调整AI参数",
            "· 搜索深度越深，AI考虑越长远，但搜索时间越长",
            "· 必胜手检测启用时，AI会优先走能直接获胜、或防守对方直接获胜的落子",
            "· 多重威胁检测启用时，AI会更多选择一次制造、或阻止对方一次制造多个高威胁棋型",
            "· 攻防倾向取值0到2，值越大AI越倾向于进攻，反之则更倾向防守",
            "· 攻防倾向不建议过大或过小，否则可能会影响游戏体验",
            "",
            "人机对战推荐配置：",
            "· 简单：搜索深度1，禁用必胜手检测，禁用多重威胁检测，攻防倾向0.8",
            "· 中等：搜索深度2，启用必胜手检测，禁用多重威胁检测，攻防倾向1.0",
            "· 困难：搜索深度3，启用必胜手检测，启用多重威胁检测，攻防倾向1.4",
            "",
            "祝您游玩愉快！"
        ]

    # ---------- 控制器初始化 ----------

    def _init_controller(self):
        """根据当前模式创建/重建对局控制器"""
        self.controller = GameController(
            use_ai=self.use_ai,
            ai_player_color=self._ai_player_color,
            ai_search_depth=self._ai_search_depth,
            ai_enable_force_win=self._ai_enable_force_win,
            ai_ad_v=self._ai_ad_v,
            ai_enable_multi_threat=self._ai_enable_multi_threat,
        )

    # ---------- 按钮初始化 ----------

    def _init_menu_buttons(self):
        center_x = WINDOW_WIDTH // 2
        btn_w, btn_h = 220, 55
        gap = 20
        start_y = WINDOW_HEIGHT // 2 - btn_h - gap // 2 - btn_h - gap + 70

        self.btn_start = Button(
            center_x - btn_w // 2, start_y,
            btn_w, btn_h, "开始游戏"
        )
        self.btn_rules = Button(
            center_x - btn_w // 2, start_y + btn_h + gap,
            btn_w, btn_h, "游戏介绍"
        )
        self.btn_mode = Button(
            center_x - btn_w // 2, start_y + 2 * (btn_h + gap),
            btn_w, btn_h, "模式选择"
        )
        self.btn_exit = Button(
            center_x - btn_w // 2, start_y + 3 * (btn_h + gap),
            btn_w, btn_h, "退出游戏"
        )

    def _init_game_buttons(self):
        panel_x = BOARD_MARGIN * 2 + BOARD_PIXEL + 10
        btn_w, btn_h = 180, 50
        gap = 15
        btn_x = panel_x + (SIDE_PANEL_WIDTH - btn_w) // 2
        start_y = 480

        self.btn_confirm = Button(btn_x, start_y + 50, btn_w, btn_h, "确认落子",
                                  COLOR_BUTTON, COLOR_BUTTON_HOVER, COLOR_BUTTON_TEXT)
        self.btn_undo_turn = Button(btn_x, start_y + btn_h + gap +50, btn_w, btn_h,
                                    "悔棋", (200, 100, 100), (220, 130, 130), COLOR_BUTTON_TEXT)

    def _init_rules_buttons(self):
        # 规则界面不需要特别按钮，用 ESC 返回
        pass

    def _init_dialog_buttons(self):
        # 确认放弃对局对话框按钮
        dialog_w, dialog_h = 360, 160
        self.dialog_rect = pygame.Rect(
            (WINDOW_WIDTH - dialog_w) // 2,
            (WINDOW_HEIGHT - dialog_h) // 2,
            dialog_w, dialog_h
        )
        btn_w, btn_h = 100, 45
        self.dialog_btn_yes = Button(
            self.dialog_rect.x + 60,
            self.dialog_rect.y + 90,
            btn_w, btn_h, "是",
            (220, 70, 70), (240, 100, 100), COLOR_BUTTON_TEXT
        )
        self.dialog_btn_no = Button(
            self.dialog_rect.x + 200,
            self.dialog_rect.y + 90,
            btn_w, btn_h, "否",
            COLOR_BUTTON, COLOR_BUTTON_HOVER, COLOR_BUTTON_TEXT
        )

    # ---------- 主循环 ----------

    def run(self):
        """主循环"""
        while self.running:
            events = pygame.event.get()
            for event in events:
                self._handle_event(event)
            self._update()
            self._draw()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()

    def _handle_event(self, event: pygame.event.Event):
        """事件分发"""
        if event.type == pygame.QUIT:
            self.running = False
            return

        if self.state == "dialog":
            self._handle_dialog_event(event)
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._handle_escape()
                return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self.state == "menu":
                self._handle_menu_click(pos)
            elif self.state == "game":
                self._handle_game_click(pos)
            elif self.state == "rules":
                self._handle_rules_click(pos)
            elif self.state == "win":
                self._handle_win_click(pos)
            elif self.state == "mode_select":
                self._handle_mode_select_click(pos)

    def _handle_escape(self):
        """ESC 键处理"""
        if self.state == "game":
            self.state = "dialog"
        elif self.state == "rules":
            self.state = "menu"
        elif self.state == "win":
            self.state = "menu"
        elif self.state == "mode_select":
            self.state = "menu"

    def _handle_dialog_event(self, event: pygame.event.Event):
        """放弃对局对话框事件处理"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = "game"
                return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self.dialog_btn_yes.is_clicked(pos):
                self.controller.start_new_game()
                self.state = "menu"
            elif self.dialog_btn_no.is_clicked(pos):
                self.state = "game"

    # ---------- 菜单 ----------

    def _handle_menu_click(self, pos: tuple[int, int]):
        if self.btn_start.is_clicked(pos):
            self.controller.start_new_game()
            self.state = "game"
        elif self.btn_rules.is_clicked(pos):
            self.state = "rules"
        elif self.btn_mode.is_clicked(pos):
            self._mode_ai_selected = self.use_ai
            self.state = "mode_select"
        elif self.btn_exit.is_clicked(pos):
            self.running = False

    # ---------- 规则 ----------

    def _handle_rules_click(self, pos: tuple[int, int]):
        pass

    # ---------- 对局 ----------

    def _handle_game_click(self, pos: tuple[int, int]):
        if self.controller.game_over:
            return

        # 如果是 AI 回合，阻止人类操作
        if not self.controller.can_human_act():
            return

        # 检查棋盘点击
        board_clicked = self._screen_to_board(pos)
        if board_clicked is not None:
            row, col = board_clicked
            if self.controller.board.is_empty(row, col):
                # 尝试落子
                if self.controller.stones_to_place > 0:
                    self.controller.place_stone(row, col)
            else:
                # 尝试撤销未确认的子
                if (row, col) in self.controller.pending_stones:
                    self.controller.undo_pending_stone(row, col)
            return

        # 确认落子按钮
        if self.btn_confirm.is_clicked(pos):
            if self.controller.confirm_move():
                # 本次确认触发了胜利
                self.state = "win"
            return

        # 悔棋按钮
        if self.btn_undo_turn.is_clicked(pos):
            if self.controller.can_undo_turn():
                self.controller.undo_turn()
            else:
                # 可以用闪烁提示，目前静默忽略
                pass
            return

    def _screen_to_board(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        """屏幕坐标转棋盘坐标"""
        mx, my = pos
        board_start_x = BOARD_MARGIN
        board_start_y = BOARD_MARGIN
        board_end_x = board_start_x + BOARD_PIXEL
        board_end_y = board_start_y + BOARD_PIXEL

        if mx < board_start_x - STONE_RADIUS or mx > board_end_x + STONE_RADIUS:
            return None
        if my < board_start_y - STONE_RADIUS or my > board_end_y + STONE_RADIUS:
            return None

        col = round((mx - board_start_x) / CELL_SIZE)
        row = round((my - board_start_y) / CELL_SIZE)
        if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
            return row, col
        return None

    # ---------- 获胜 ----------

    def _handle_win_click(self, pos: tuple[int, int]):
        # 获胜界面按任意位置不处理，ESC 返回
        pass

    # ---------- 更新 ----------

    def _update(self):
        if self.state == "game":
            ctrl = self.controller
            if ctrl.use_ai:
                ctrl.ai_tick()
                # AI 触发胜利后切换到 win 状态
                if ctrl.game_over and self.state == "game":
                    self.state = "win"
    # ---------- 绘制 ----------

    # ---------- 绘制 ----------

    def _draw(self):
        if self.state == "menu":
            self._draw_menu()
        elif self.state == "rules":
            self._draw_rules()
        elif self.state == "mode_select":
            self._draw_mode_select()
        elif self.state == "game":
            self._draw_game()
        elif self.state == "win":
            # 先绘制游戏界面（作为底层），再叠加获胜条带
            self._draw_game()
            self._draw_win_banner()
        elif self.state == "dialog":
            # 先绘制游戏界面（作为底层）
            self._draw_game()
            self._draw_dialog()

        pygame.display.flip()

    def _draw_menu(self):
        """绘制主菜单"""
        self.screen.fill(COLOR_PANEL_BG)
        title_surf = self.font_title.render("六子棋 - Connect6", True, COLOR_TITLE)
        title_rect = title_surf.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 140))
        self.screen.blit(title_surf, title_rect)

        self.btn_start.draw(self.screen, self.font_button)
        self.btn_rules.draw(self.screen, self.font_button)
        self.btn_mode.draw(self.screen, self.font_button)
        self.btn_exit.draw(self.screen, self.font_button)

    def _draw_rules(self):
        """绘制规则介绍界面"""
        self.screen.fill(COLOR_PANEL_BG)
        y_offset = 30
        for line in self.rules_text_lines:
            if line.startswith("六子棋"):
                surf = self.font_subtitle.render(line, True, COLOR_TITLE)
            elif line == "":
                y_offset += 10
                continue
            else:
                surf = self.font_text.render(line, True, COLOR_TEXT)
            rect = surf.get_rect(topleft=(40, y_offset))
            self.screen.blit(surf, rect)
            y_offset += surf.get_height() + 6

        # 底部提示
        hint_surf = self.font_small.render("按 ESC 键返回主菜单", True, (100, 100, 100))
        hint_rect = hint_surf.get_rect(bottomright=(WINDOW_WIDTH - 20, WINDOW_HEIGHT - 20))
        self.screen.blit(hint_surf, hint_rect)

    # ---------- 模式选择 ----------

    def _handle_mode_select_click(self, pos: tuple[int, int]):
        """处理模式选择界面点击"""
        center_x = WINDOW_WIDTH // 2
        row_w, row_h = 340, 45
        gap = 16

        # --- 与 _draw_mode_select 完全一致的布局计算 ---
        section_y = 120
        mode_start_y = section_y + 32

        # 模式选择行
        row_ai_rect = pygame.Rect(center_x - row_w // 2, mode_start_y, row_w, row_h)
        row_pvp_rect = pygame.Rect(center_x - row_w // 2, mode_start_y + row_h + gap, row_w, row_h)

        if row_ai_rect.collidepoint(pos):
            self._mode_ai_selected = True
            self.use_ai = True
            self._init_controller()
        elif row_pvp_rect.collidepoint(pos):
            self._mode_ai_selected = False
            self.use_ai = False
            self._init_controller()

        # AI 颜色（仅人机模式可见）
        if self._mode_ai_selected:
            color_section_y = mode_start_y + 2 * (row_h + gap) + 9
            color_start_y = color_section_y + 27
            half_w = row_w // 2 - 10

            row_black_rect = pygame.Rect(center_x - row_w // 2, color_start_y, half_w, row_h)
            row_white_rect = pygame.Rect(center_x + 20, color_start_y, half_w, row_h)

            if row_black_rect.collidepoint(pos):
                self._ai_player_color = BLACK
                self._init_controller()
            elif row_white_rect.collidepoint(pos):
                self._ai_player_color = WHITE
                self._init_controller()

            # AI 搜索深度
            depth_section_y = color_start_y + row_h + gap + 9
            depth_start_y = depth_section_y + 27
            depth_btn_w = (row_w - 40) // 3
            depth_keys = ["1", "2", "3"]
            for i, key in enumerate(depth_keys):
                btn_x = center_x - row_w // 2 + i * (depth_btn_w + 20)
                btn_rect = pygame.Rect(btn_x, depth_start_y, depth_btn_w, row_h)
                if btn_rect.collidepoint(pos):
                    self._ai_search_depth = int(key)
                    self._init_controller()

            # 必胜手检测
            force_win_y = depth_start_y + row_h + gap + 9
            force_start_y = force_win_y + 27
            force_btn_w = (row_w - 20) // 2
            for i, (label, val) in enumerate([("禁用", False), ("启用", True)]):
                btn_x = center_x - row_w // 2 + i * (force_btn_w + 20)
                btn_rect = pygame.Rect(btn_x, force_start_y, force_btn_w, row_h)
                if btn_rect.collidepoint(pos):
                    self._ai_enable_force_win = val
                    self._init_controller()

            # 多重威胁检测
            multi_threat_y = force_start_y + row_h + gap + 9
            multi_start_y = multi_threat_y + 27
            multi_btn_w = (row_w - 20) // 2
            for i, (label, val) in enumerate([("禁用", False), ("启用", True)]):
                btn_x = center_x - row_w // 2 + i * (multi_btn_w + 20)
                btn_rect = pygame.Rect(btn_x, multi_start_y, multi_btn_w, row_h)
                if btn_rect.collidepoint(pos):
                    self._ai_enable_multi_threat = val
                    self._init_controller()
            
            # 攻防倾向
            ad_v_y = multi_start_y + row_h + gap + 9
            ad_v_start_y = ad_v_y + 27
            ad_v_btn_w = (row_w - 40) // 4
            ad_v_deltas = [-0.5, -0.1, +0.1, +0.5]
            ad_v_labels = ["-0.5", "-0.1", "+0.1", "+0.5"]
            for i, (label, delta) in enumerate(zip(ad_v_labels, ad_v_deltas)):
                btn_x = center_x - row_w // 2 + i * (ad_v_btn_w + 13)
                btn_rect = pygame.Rect(btn_x, ad_v_start_y, ad_v_btn_w, row_h)
                if btn_rect.collidepoint(pos):
                    new_val = round(self._ai_ad_v + delta, 1)
                    new_val = max(0.0, min(2.0, new_val))
                    self._ai_ad_v = new_val
                    self._init_controller()

            

    def _draw_mode_select(self):
        """绘制模式选择界面"""
        self.screen.fill(COLOR_PANEL_BG)

        # 标题
        title_surf = self.font_title.render("模式选择", True, COLOR_TITLE)
        title_rect = title_surf.get_rect(center=(WINDOW_WIDTH // 2, 60))
        self.screen.blit(title_surf, title_rect)

        center_x = WINDOW_WIDTH // 2
        row_w, row_h = 340, 45
        gap = 16
        mouse_pos = pygame.mouse.get_pos()

        # ---- 模式选择（人机对战 / 双人对战） ----
        section_y = 120
        section_surf = self.font_text.render("对战模式", True, (60, 60, 60))
        section_rect = section_surf.get_rect(midleft=(center_x - row_w // 2, section_y))
        self.screen.blit(section_surf, section_rect)

        mode_start_y = section_y + 32
        options = [
            ("人机对战", True, mode_start_y),
            ("双人对战", False, mode_start_y + row_h + gap),
        ]

        for text, is_ai, y in options:
            row_rect = pygame.Rect(center_x - row_w // 2, y, row_w, row_h)
            hovered = row_rect.collidepoint(mouse_pos)

            bg = (70, 130, 180) if hovered else (48, 60, 80)
            pygame.draw.rect(self.screen, bg, row_rect, border_radius=8)
            pygame.draw.rect(self.screen, (160, 160, 180), row_rect, width=2, border_radius=8)

            # 勾选框
            checkbox_size = 22
            checkbox_x = row_rect.x + 18
            checkbox_y = row_rect.centery - checkbox_size // 2
            checkbox_rect = pygame.Rect(checkbox_x, checkbox_y, checkbox_size, checkbox_size)

            selected = (self._mode_ai_selected and is_ai) or (not self._mode_ai_selected and not is_ai)

            pygame.draw.rect(self.screen, (255, 255, 255), checkbox_rect, border_radius=3)
            pygame.draw.rect(self.screen, (0, 0, 0), checkbox_rect, width=2, border_radius=3)
            if selected:
                cx = checkbox_rect.centerx
                cy = checkbox_rect.centery
                pts = [
                    (cx - 6, cy),
                    (cx - 2, cy + 5),
                    (cx + 7, cy - 5),
                ]
                pygame.draw.lines(self.screen, (0, 200, 0), False, pts, width=3)

            text_surf = self.font_text.render(text, True, (255, 255, 255))
            text_rect = text_surf.get_rect(
                midleft=(checkbox_x + checkbox_size + 15, row_rect.centery)
            )
            self.screen.blit(text_surf, text_rect)

        # ---- AI 相关选项（仅人机对战） ----
        if self._mode_ai_selected:
            # AI 颜色
            color_section_y = mode_start_y + 2 * (row_h + gap) + 9
            color_surf = self.font_text.render("AI 执子", True, (60, 60, 60))
            color_rect = color_surf.get_rect(midleft=(center_x - row_w // 2, color_section_y))
            self.screen.blit(color_surf, color_rect)

            color_start_y = color_section_y + 27
            half_w = row_w // 2 - 10
            color_opts = [
                ("执黑（先手）", BLACK, center_x - row_w // 2, color_start_y, half_w),
                ("执白（后手）", WHITE, center_x + 20, color_start_y, half_w),
            ]
            for label, col_val, bx, by, bw in color_opts:
                btn_rect = pygame.Rect(bx, by, bw, row_h)
                hovered = btn_rect.collidepoint(mouse_pos)
                selected = (self._ai_player_color == col_val)
                bg = (60, 120, 60) if selected else ((80, 140, 80) if hovered else (48, 60, 48))
                pygame.draw.rect(self.screen, bg, btn_rect, border_radius=8)
                pygame.draw.rect(self.screen, (0, 0, 0) if not selected else (255, 255, 0),
                                 btn_rect, width=2, border_radius=8)
                label_surf = self.font_small.render(label, True, (255, 255, 255))
                label_rect = label_surf.get_rect(center=btn_rect.center)
                self.screen.blit(label_surf, label_rect)

            # AI 搜索深度
            depth_section_y = color_start_y + row_h + gap + 9
            depth_surf = self.font_text.render("搜索深度", True, (60, 60, 60))
            depth_rect = depth_surf.get_rect(midleft=(center_x - row_w // 2, depth_section_y))
            self.screen.blit(depth_surf, depth_rect)

            depth_start_y = depth_section_y + 27
            depth_btn_w = (row_w - 40) // 3
            depth_keys = ["1", "2", "3"]
            depth_colors_base = {
                "1": (60, 100, 60),
                "2": (100, 100, 40),
                "3": (120, 50, 50),
            }
            for i, key in enumerate(depth_keys):
                btn_x = center_x - row_w // 2 + i * (depth_btn_w + 20)
                btn_rect = pygame.Rect(btn_x, depth_start_y, depth_btn_w, row_h)
                hovered = btn_rect.collidepoint(mouse_pos)
                selected = (self._ai_search_depth == int(key))
                base = depth_colors_base[key]
                bg = tuple(min(c + 30, 255) for c in base) if selected else (
                    tuple(min(c + 50, 255) for c in base) if hovered else base)
                pygame.draw.rect(self.screen, bg, btn_rect, border_radius=8)
                pygame.draw.rect(self.screen, (0, 0, 0) if not selected else (255, 255, 0),
                                 btn_rect, width=2, border_radius=8)
                label_surf = self.font_small.render(key, True, (255, 255, 255))
                label_rect = label_surf.get_rect(center=btn_rect.center)
                self.screen.blit(label_surf, label_rect)

            # 必胜手检测
            force_win_y = depth_start_y + row_h + gap + 9
            force_surf = self.font_text.render("必胜手检测", True, (60, 60, 60))
            force_rect = force_surf.get_rect(midleft=(center_x - row_w // 2, force_win_y))
            self.screen.blit(force_surf, force_rect)

            force_start_y = force_win_y + 27
            force_btn_w = (row_w - 20) // 2
            for i, (label, val) in enumerate([("禁用", False), ("启用", True)]):
                btn_x = center_x - row_w // 2 + i * (force_btn_w + 20)
                btn_rect = pygame.Rect(btn_x, force_start_y, force_btn_w, row_h)
                hovered = btn_rect.collidepoint(mouse_pos)
                selected = (self._ai_enable_force_win == val)
                base_color = (60, 100, 60) if val else (120, 50, 50)
                bg = tuple(min(c + 30, 255) for c in base_color) if selected else (
                    tuple(min(c + 50, 255) for c in base_color) if hovered else base_color)
                pygame.draw.rect(self.screen, bg, btn_rect, border_radius=8)
                pygame.draw.rect(self.screen, (0, 0, 0) if not selected else (255, 255, 0),
                                 btn_rect, width=2, border_radius=8)
                label_surf = self.font_small.render(label, True, (255, 255, 255))
                label_rect = label_surf.get_rect(center=btn_rect.center)
                self.screen.blit(label_surf, label_rect)

            # 多重威胁检测
            multi_threat_y = force_start_y + row_h + gap + 9
            multi_surf = self.font_text.render("多重威胁检测", True, (60, 60, 60))
            multi_rect = multi_surf.get_rect(midleft=(center_x - row_w // 2, multi_threat_y))
            self.screen.blit(multi_surf, multi_rect)

            multi_start_y = multi_threat_y + 27
            multi_btn_w = (row_w - 20) // 2
            for i, (label, val) in enumerate([("禁用", False), ("启用", True)]):
                btn_x = center_x - row_w // 2 + i * (multi_btn_w + 20)
                btn_rect = pygame.Rect(btn_x, multi_start_y, multi_btn_w, row_h)
                hovered = btn_rect.collidepoint(mouse_pos)
                selected = (self._ai_enable_multi_threat == val)
                base_color = (60, 100, 60) if val else (120, 50, 50)
                bg = tuple(min(c + 30, 255) for c in base_color) if selected else (
                    tuple(min(c + 50, 255) for c in base_color) if hovered else base_color)
                pygame.draw.rect(self.screen, bg, btn_rect, border_radius=8)
                pygame.draw.rect(self.screen, (0, 0, 0) if not selected else (255, 255, 0),
                                 btn_rect, width=2, border_radius=8)
                label_surf = self.font_small.render(label, True, (255, 255, 255))
                label_rect = label_surf.get_rect(center=btn_rect.center)
                self.screen.blit(label_surf, label_rect)
            
            # 攻防倾向
            ad_v_y = multi_start_y + row_h + gap + 9
            ad_v_surf = self.font_text.render(
                f"攻防倾向 (当前：{self._ai_ad_v:.1f})", True, (60, 60, 60))
            ad_v_rect = ad_v_surf.get_rect(midleft=(center_x - row_w // 2, ad_v_y))
            self.screen.blit(ad_v_surf, ad_v_rect)

            ad_v_start_y = ad_v_y + 27
            ad_v_btn_w = (row_w - 40) // 4
            ad_v_deltas = [-0.5, -0.1, +0.1, +0.5]
            ad_v_labels = ["-0.5", "-0.1", "+0.1", "+0.5"]
            for i, (label, delta) in enumerate(zip(ad_v_labels, ad_v_deltas)):
                btn_x = center_x - row_w // 2 + i * (ad_v_btn_w + 13)
                btn_rect = pygame.Rect(btn_x, ad_v_start_y, ad_v_btn_w, row_h)
                hovered = btn_rect.collidepoint(mouse_pos)
                base_color = (80, 80, 120)
                bg = tuple(min(c + 50, 255) for c in base_color) if hovered else base_color
                pygame.draw.rect(self.screen, bg, btn_rect, border_radius=8)
                pygame.draw.rect(self.screen, (160, 160, 200),
                                 btn_rect, width=2, border_radius=8)
                label_surf = self.font_small.render(label, True, (255, 255, 255))
                label_rect = label_surf.get_rect(center=btn_rect.center)
                self.screen.blit(label_surf, label_rect)

            

        # 底部 ESC 提示
        hint_surf = self.font_small.render("按 ESC 键返回主菜单", True, (100, 100, 100))
        hint_rect = hint_surf.get_rect(bottomright=(WINDOW_WIDTH - 20, WINDOW_HEIGHT - 20))
        self.screen.blit(hint_surf, hint_rect)

    # ---------- 对局界面 ----------

    def _draw_game(self):
        """绘制对局界面"""
        self.screen.fill(COLOR_BOARD)

        # 绘制棋盘
        self._draw_board()
        # 绘制棋子
        self._draw_stones()
        # 绘制高亮
        self._draw_highlights()
        # 绘制右侧面板
        self._draw_side_panel()

    def _draw_board(self):
        """绘制棋盘网格和坐标"""
        start_x = BOARD_MARGIN
        start_y = BOARD_MARGIN

        # 绘制网格线
        for i in range(BOARD_SIZE):
            # 横线
            y = start_y + i * CELL_SIZE
            pygame.draw.line(self.screen, COLOR_LINE,
                             (start_x, y), (start_x + BOARD_PIXEL, y), 1)
            # 竖线
            x = start_x + i * CELL_SIZE
            pygame.draw.line(self.screen, COLOR_LINE,
                             (x, start_y), (x, start_y + BOARD_PIXEL), 1)

        # 绘制星位
        for (r, c) in STAR_POINTS:
            sx = start_x + c * CELL_SIZE
            sy = start_y + r * CELL_SIZE
            pygame.draw.circle(self.screen, COLOR_STAR, (sx, sy), 4)

        # 绘制坐标标签
        col_labels = "ABCDEFGHIJKLMNOPQRS"
        for i in range(BOARD_SIZE):
            # 列标签（上方和下方）
            x = start_x + i * CELL_SIZE
            label = self.font_small.render(col_labels[i], True, COLOR_LABEL)
            lr = label.get_rect(center=(x, start_y - BOARD_MARGIN // 2))
            self.screen.blit(label, lr)
            lr2 = label.get_rect(center=(x, start_y + BOARD_PIXEL + BOARD_MARGIN // 2))
            self.screen.blit(label, lr2)
            # 行标签（左侧和右侧）
            y = start_y + i * CELL_SIZE
            row_label = self.font_small.render(str(BOARD_SIZE - i), True, COLOR_LABEL)
            rl_rect = row_label.get_rect(center=(start_x - BOARD_MARGIN // 2, y))
            self.screen.blit(row_label, rl_rect)
            rl_rect2 = row_label.get_rect(
                center=(start_x + BOARD_PIXEL + BOARD_MARGIN // 2, y))
            self.screen.blit(row_label, rl_rect2)

    def _draw_stones(self):
        """绘制所有棋子"""
        start_x = BOARD_MARGIN
        start_y = BOARD_MARGIN
        board = self.controller.board

        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                cell = board.get_cell(r, c)
                if cell == EMPTY:
                    continue
                sx = start_x + c * CELL_SIZE
                sy = start_y + r * CELL_SIZE
                color = COLOR_BLACK if cell == BLACK else COLOR_WHITE
                pygame.draw.circle(self.screen, color, (sx, sy), STONE_RADIUS)
                if cell == WHITE:
                    # 白子加黑色边框便于区分
                    pygame.draw.circle(self.screen, COLOR_LINE, (sx, sy), STONE_RADIUS, 1)

    def _draw_highlights(self):
        """绘制高亮轮廓（未确认 + 已确认的持久高亮）"""
        if self.controller.game_over:
            return
        start_x = BOARD_MARGIN
        start_y = BOARD_MARGIN

        for (r, c) in self.controller.highlighted_stones:
            player = self.controller.board.get_cell(r, c)
            sx = start_x + c * CELL_SIZE
            sy = start_y + r * CELL_SIZE
            if player == BLACK:
                outline_color = COLOR_HIGHLIGHT_BLACK
            elif player == WHITE:
                outline_color = COLOR_HIGHLIGHT_WHITE
            else:
                continue
            # 绘制高亮轮廓
            pygame.draw.circle(self.screen, outline_color,
                               (sx, sy), STONE_RADIUS + 3, width=3)

    def _draw_side_panel(self):
        """绘制右侧信息面板"""
        panel_x = BOARD_MARGIN * 2 + BOARD_PIXEL + 10
        panel_w = SIDE_PANEL_WIDTH
        panel_h = WINDOW_HEIGHT - 60
        panel_y = 30

        # 面板背景
        pygame.draw.rect(self.screen, COLOR_PANEL_BG,
                         (panel_x, panel_y, panel_w, panel_h), border_radius=10)
        pygame.draw.rect(self.screen, (0, 0, 0),
                         (panel_x, panel_y, panel_w, panel_h), width=2, border_radius=10)

        # 当前行动方
        if not self.controller.game_over:
            current_name = self.controller.get_current_color_name()
        else:
            current_name = self.controller.get_winner_name() + " 获胜！"

        turn_surf = self.font_text.render("当前行动：", True, COLOR_TEXT)
        self.screen.blit(turn_surf, (panel_x + 10, panel_y + 20))

        # 当前行动方颜色指示
        if self.controller.current_player == BLACK:
            player_color = COLOR_BLACK
        else:
            player_color = COLOR_WHITE
        pygame.draw.circle(self.screen, player_color,
                           (panel_x + panel_w // 2, panel_y + 75), 20)
        if self.controller.current_player == WHITE:
            pygame.draw.circle(self.screen, COLOR_LINE,
                               (panel_x + panel_w // 2, panel_y + 75), 20, 1)

        name_surf = self.font_text.render(current_name, True, COLOR_TITLE)
        name_rect = name_surf.get_rect(center=(panel_x + panel_w // 2, panel_y + 115))
        self.screen.blit(name_surf, name_rect)

        # 轮次信息
        turn_num_surf = self.font_small.render(
            f"轮次：第 {self.controller.turn_number + 1} 轮",
            True, COLOR_TEXT
        )
        self.screen.blit(turn_num_surf, (panel_x + 10, panel_y + 145))

        # 落子提示
        if not self.controller.game_over:
            remain = self.controller.stones_to_place
            stones_text = f"本轮还需落 {remain} 子"
            hint_surf = self.font_small.render(stones_text, True, COLOR_TEXT)
            self.screen.blit(hint_surf, (panel_x + 10, panel_y + 175))

            # 未确认落子数
            pending_count = len(self.controller.pending_stones)
            pending_surf = self.font_small.render(
                f"未确认：{pending_count} 子", True,
                (200, 80, 20) if pending_count > 0 else COLOR_TEXT
            )
            self.screen.blit(pending_surf, (panel_x + 10, panel_y + 200))

        # ---- AI 思考中提示 ----
        if self.controller.ai_thinking:
            import time
            if int(time.time() * 2) % 2:  # 闪烁效果
                ai_surf = self.font_text.render("AI 思考中...", True, (165, 110, 0))
                ai_rect = ai_surf.get_rect(
                    center=(panel_x + panel_w // 2, panel_y + 410)
                )
                self.screen.blit(ai_surf, ai_rect)
        # ---------------------------

        # 悔棋状态
        if not self.controller.game_over and self.controller.turn_number > 0:
            undo_text = "悔棋可用" if self.controller.can_undo_turn() else "悔棋不可用"
            undo_color = (0, 120, 0) if self.controller.can_undo_turn() else (180, 60, 60)
            undo_surf = self.font_small.render(undo_text, True, undo_color)
            self.screen.blit(undo_surf, (panel_x + 10, panel_y + 230))

        # ---- AI 信息（仅人机对战模式显示） ----
        if self.controller.use_ai:
            ai_color_names = {BLACK: "执黑", WHITE: "执白"}
            ai_info_y = panel_y + 270

            # 分隔线
            pygame.draw.line(self.screen, (180, 180, 180),
                             (panel_x + 10, ai_info_y-10),
                             (panel_x + panel_w - 10, ai_info_y-10), 1)
            
            pygame.draw.line(self.screen, (180, 180, 180),
                             (panel_x + 10, ai_info_y+170),
                             (panel_x + panel_w - 10, ai_info_y+170), 1)

            ai_info_y += 10
            # AI 执方
            color_text = f"AI 执方：{ai_color_names.get(self.controller.ai_player_color, '未知')}"
            color_surf = self.font_small.render(color_text, True, (80, 80, 160))
            self.screen.blit(color_surf, (panel_x + 10, ai_info_y))

            ai_info_y += 22
            # AI 搜索深度
            depth_text = f"搜索深度：{self.controller.ai_search_depth}"
            depth_surf = self.font_small.render(depth_text, True, (160, 80, 20))
            self.screen.blit(depth_surf, (panel_x + 10, ai_info_y))

            ai_info_y += 22
            # 必胜手检测
            force_text = f"必胜手检测：{'启用' if self.controller.ai_enable_force_win else '禁用'}"
            force_surf = self.font_small.render(force_text, True, (200, 60, 60) if not self.controller.ai_enable_force_win else (60, 120, 60))
            self.screen.blit(force_surf, (panel_x + 10, ai_info_y))

            ai_info_y += 22
            # 多重威胁检测
            multi_text = f"多重威胁检测：{'启用' if self.controller.ai_enable_multi_threat else '禁用'}"
            multi_color = (200, 60, 60) if not self.controller.ai_enable_multi_threat else (60, 120, 60)
            multi_surf = self.font_small.render(multi_text, True, multi_color)
            self.screen.blit(multi_surf, (panel_x + 10, ai_info_y))
            
            
            ai_info_y += 22
            # 攻防倾向
            ad_v_val = self.controller.ad_v
            if ad_v_val < 0.7:
                ad_v_color = (80, 120, 200)  # 偏防守 - 蓝色
                ad_tendency = "偏防守"
            elif ad_v_val > 1.3:
                ad_v_color = (200, 80, 80)  # 偏进攻 - 红色
                ad_tendency = "偏进攻"
            else:
                ad_v_color = (100, 160, 100)  # 均衡 - 绿色
                ad_tendency = "均衡"
            ad_v_text = f"攻防倾向：{ad_v_val:.1f} ({ad_tendency})"
            ad_v_surf = self.font_small.render(ad_v_text, True, ad_v_color)
            self.screen.blit(ad_v_surf, (panel_x + 10, ai_info_y))

            

        # 按钮
        self.btn_confirm.draw(self.screen, self.font_button)
        self.btn_undo_turn.draw(self.screen, self.font_button)

        # 底部 ESC 提示
        hint_surf = self.font_small.render("ESC 放弃对局", True, (120, 120, 120))
        hint_rect = hint_surf.get_rect(
            center=(panel_x + panel_w // 2, panel_y + panel_h - 20)
        )
        self.screen.blit(hint_surf, hint_rect)

    def _draw_win_banner(self):
        """在棋盘界面上方绘制获胜条带"""
        banner_height = 160
        banner_y = (WINDOW_HEIGHT - banner_height) // 2

        # 半透明黑色条带背景
        banner_surf = pygame.Surface((WINDOW_WIDTH, banner_height), pygame.SRCALPHA)
        banner_surf.fill((0, 0, 0, 180))
        self.screen.blit(banner_surf, (0, banner_y))

        # 获胜文字（金色）
        winner_name = self.controller.get_winner_name()
        win_text = f"{winner_name}获胜！"
        win_surf = self.font_win.render(win_text, True, (255, 215, 0))
        win_rect = win_surf.get_rect(
            center=(WINDOW_WIDTH // 2, banner_y + banner_height // 2)
        )
        self.screen.blit(win_surf, win_rect)

        # ESC 提示（位于条带内底部）
        hint_surf = self.font_small.render("按 ESC 键返回主菜单", True, (180, 180, 180))
        hint_rect = hint_surf.get_rect(
            center=(WINDOW_WIDTH // 2, banner_y + banner_height - 15)
        )
        self.screen.blit(hint_surf, hint_rect)

    def _draw_dialog(self):
        """绘制确认放弃对局对话框"""
        # 半透明背景遮罩
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill(COLOR_OVERLAY)
        self.screen.blit(overlay, (0, 0))

        # 对话框背景
        pygame.draw.rect(self.screen, (240, 240, 240), self.dialog_rect, border_radius=12)
        pygame.draw.rect(self.screen, (0, 0, 0), self.dialog_rect, width=2, border_radius=12)

        # 文本
        prompt = self.font_text.render("是否放弃对局？", True, COLOR_TITLE)
        prompt_rect = prompt.get_rect(
            center=(self.dialog_rect.centerx, self.dialog_rect.y + 50)
        )
        self.screen.blit(prompt, prompt_rect)

        # 按钮
        self.dialog_btn_yes.draw(self.screen, self.font_button)
        self.dialog_btn_no.draw(self.screen, self.font_button)