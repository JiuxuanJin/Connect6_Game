"""
connect6 对局控制器模块
回合管理、胜负判断、悔棋等功能
纯逻辑，零 GUI 依赖
"""

import threading
from .config import BLACK, WHITE, EMPTY, BOARD_SIZE
from .board import Board


class GameController:
    """对局控制器"""

    def __init__(self, use_ai: bool = False, ai_player_color: int = WHITE,
                 ai_search_depth: int = 1, ai_enable_force_win: bool = False,
                 ai_ad_v: float = 1.0, ai_enable_multi_threat: bool = False):
        self.board = Board()
        self.current_player = BLACK      # 当前行动方
        self.turn_number = 0             # 当前轮次编号（从0开始）
        self.stones_to_place = 0         # 当前回合还需落子数
        self.pending_stones: list[tuple[int, int]] = []  # 本轮新落但未确认的子
        self.winner = EMPTY              # EMPTY=对局中, BLACK/WHITE=获胜方
        self.game_over = False
        self._undo_used_this_turn = False

        # AI 模式
        self.use_ai = use_ai
        self.ai_player_color = ai_player_color
        self.ai_search_depth = ai_search_depth
        self.ai_enable_force_win = ai_enable_force_win
        self.ai_ad_v = ai_ad_v
        self.ai_enable_multi_threat = ai_enable_multi_threat

        self._ai: object | None = None
        if use_ai:
            from .ai import AIPlayer
            self._ai = AIPlayer(
                player_color=ai_player_color,
                search_depth=ai_search_depth,
                enable_force_win_detection=ai_enable_force_win,
                ad_v=ai_ad_v,
                enable_multi_threat=ai_enable_multi_threat,
            )

        # AI 后台线程
        self._ai_thinking = False       # AI 是否正在后台思考（含计算阶段）
        self._ai_thread: threading.Thread | None = None
        self._ai_result: list[tuple[int, int]] | None = None  # 线程计算结果
        self._ai_move_display_timer = 0  # AI 落子显示计时器
        self._ai_needs_confirm = False   # AI 落子完成后需确认
        self._ai_display_phase = 0       # 0=无, 1=等待显示第1子, 2=显示第1子等待, 3=显示第2子等待, 4=待确认
        self._ai_pending_moves: list[tuple[int, int]] = []  # AI 待展示的落子

        # highlight 持续机制：每位玩家最近一次 confirm 的落子一直被高亮，
        # 直到该玩家开始下一轮行动时才清除。
        self._player_confirmed_highlights: dict[int, set[tuple[int, int]]] = {
            BLACK: set(), WHITE: set()
        }
        self.highlighted_stones: set[tuple[int, int]] = set()  # 供 GUI 直接读取
        self._update_highlights()

        # 悔棋快照队列：每次 confirm 后推入一份棋盘副本，保留最近3份
        # undo 时使用最旧的那一份（下标0），代表 2 回合前的状态
        self._snapshots: list[Board] = []

    # ---------- 对局初始化 ----------

    def start_new_game(self):
        """开始新游戏"""
        self._cancel_ai_thinking()
        self.board.clear()
        self.current_player = BLACK
        self.turn_number = 0
        self.stones_to_place = 1          # 黑方第一手落1子
        self.pending_stones.clear()
        self.winner = EMPTY
        self.game_over = False
        self._undo_used_this_turn = False
        self._player_confirmed_highlights[BLACK].clear()
        self._player_confirmed_highlights[WHITE].clear()
        self._update_highlights()
        self._snapshots.clear()
        self._ai_thinking = False
        self._ai_result = None
        self._ai_move_display_timer = 0
        self._ai_needs_confirm = False
        self._ai_display_phase = 0
        self._ai_pending_moves.clear()

    def _start_turn(self):
        """开始新回合（内部调用）"""
        self._undo_used_this_turn = False
        self.pending_stones.clear()

        # 清除“本方”上一次 confirm 的持久高亮
        self._player_confirmed_highlights[self.current_player].clear()
        self._update_highlights()

        if self.turn_number == 0:
            self.stones_to_place = 1
        else:
            self.stones_to_place = 2

    # ---------- 落子相关 ----------

    def place_stone(self, row: int, col: int) -> bool:
        """尝试在指定位置落子（当前未确认阶段），成功返回 True"""
        if self.game_over:
            return False
        if self.stones_to_place <= 0:
            return False
        if not self.board.is_empty(row, col):
            return False

        self.board.place_stone(row, col, self.current_player)
        self.pending_stones.append((row, col))
        self.stones_to_place -= 1
        self._update_highlights()
        return True

    def can_undo_pending(self) -> bool:
        """是否可以撤销未确认的落子"""
        return len(self.pending_stones) > 0

    def undo_pending_stone(self, row: int, col: int) -> bool:
        """撤销某个未确认的落子（点击已落的子来撤销）"""
        if (row, col) not in self.pending_stones:
            return False
        self.pending_stones.remove((row, col))
        self.board.remove_stone(row, col)
        self.stones_to_place += 1
        self._update_highlights()
        return True

    # ---------- 确认落子 ----------

    def confirm_move(self) -> bool:
        """确认落子，切换到对方回合。返回是否触发胜利"""
        if self.stones_to_place > 0:
            return False
        if self.game_over:
            return False

        # 检查每个新落子是否形成六连
        for (r, c) in self.pending_stones:
            if self.board.check_win(r, c):
                self.winner = self.current_player
                self.game_over = True
                self.pending_stones.clear()
                self._update_highlights()
                return True

        # 将刚才 confirm 的落子加入本方持久高亮
        for pos in self.pending_stones:
            self._player_confirmed_highlights[self.current_player].add(pos)

        # 保存悔棋快照（confirm 完成后、切换前）
        self._push_snapshot()

        self.pending_stones.clear()
        self._switch_player()
        self._update_highlights()
        return False

    def _push_snapshot(self):
        """推入悔棋快照，保持最近3份"""
        self._snapshots.append(self.board.copy())
        if len(self._snapshots) > 3:
            self._snapshots.pop(0)

    # ---------- 内部辅助 ----------

    def _switch_player(self):
        """切换行动方并开始新回合"""
        self.current_player = WHITE if self.current_player == BLACK else BLACK
        self.turn_number += 1
        self._start_turn()

    def _update_highlights(self):
        """更新综合高亮集合"""
        self.highlighted_stones = (
            set(self.pending_stones)
            | self._player_confirmed_highlights[BLACK]
            | self._player_confirmed_highlights[WHITE]
        )

    # ---------- 悔棋 ----------

    def can_undo_turn(self) -> bool:
        """检查当前回合是否可以使用悔棋"""
        if self.game_over:
            return False
        if self._undo_used_this_turn:
            return False
        if self.turn_number < 4:
            return False
        if len(self._snapshots) < 3:
            return False
        return True

    def undo_turn(self) -> bool:
        """
        悔棋：撤销上两轮的行动。
        黑方悔棋 → 移除黑方未确认落子、移除白方最近2颗、
                    移除黑方最近2颗，轮次-2，黑方行动。
        白方悔棋同理。
        """
        if not self.can_undo_turn():
            return False

        # 1. 移除本方未确认落子
        for (r, c) in self.pending_stones:
            self.board.remove_stone(r, c)
        self.pending_stones.clear()

        # 2. 恢复到 2 回合前的棋盘快照
        self.board.restore_from(self._snapshots[0])

        # 3. 回退轮次（-2）
        self.turn_number -= 2
        # 不回退 current_player：当前玩家不变，重新行动

        # 4. 清除所有持久高亮（历史快照中已不含这些落子）
        self._player_confirmed_highlights[BLACK].clear()
        self._player_confirmed_highlights[WHITE].clear()

        # 5. 重置回合状态
        self.stones_to_place = 2  # 回退后 turn_number >= 3，都是2子
        self._undo_used_this_turn = True
        self._snapshots.clear()   # 清空快照，后续 confirm 重新积累
        self._update_highlights()
        return True

    # ---------- 查询 ----------

    def get_current_color_name(self) -> str:
        """获取当前行动方名称"""
        return "黑方" if self.current_player == BLACK else "白方"

    def get_winner_name(self) -> str:
        """获取获胜方名称"""
        if self.winner == BLACK:
            return "黑方"
        elif self.winner == WHITE:
            return "白方"
        return ""

    # ---------- AI 相关 ----------

    def is_ai_turn(self) -> bool:
        """当前是否为 AI 回合"""
        return (
            self.use_ai
            and not self.game_over
            and self.current_player == self.ai_player_color
        )

    def can_human_act(self) -> bool:
        """人类玩家是否可以进行操作（非 AI 回合、非对局结束）"""
        if self.game_over:
            return False
        return not self.is_ai_turn()

    @property
    def ad_v(self) -> float:
        """攻防倾向（0=完全防守，2=完全进攻）"""
        return self.ai_ad_v

    @property
    def ai_thinking(self) -> bool:
        """AI 是否正在思考或显示落子过程中（用于 GUI 显示"AI 思考中…"）"""
        return self._ai_thinking or self._ai_display_phase > 0 or self._ai_needs_confirm

    def _start_ai_thinking(self):
        """在后台线程启动 AI 计算"""
        if self._ai is None or self._ai_thinking:
            return

        self._ai_thinking = True
        self._ai_result = None
        # 拷贝必要数据，避免线程间数据竞争
        board_copy = self.board.copy()
        stones = self.stones_to_place
        ai_ref = self._ai
        # AI 执黑第一步使用加权随机星位，无需线程
        if stones == 1 and self.turn_number == 0 and self.ai_player_color == BLACK:
            try:
                result = ai_ref.get_first_move_as_black()
                self._ai_result = result
            except Exception:
                self._ai_result = None
            self._ai_thinking = False
            return

        def _run():
            try:
                result = ai_ref.get_move(board_copy, stones)
                self._ai_result = result
            except Exception:
                self._ai_result = None
            finally:
                self._ai_thinking = False

        self._ai_thread = threading.Thread(target=_run, daemon=True)
        self._ai_thread.start()

    def _cancel_ai_thinking(self):
        """取消 AI 思考（不 join，因为 daemon 线程会自动结束）"""
        self._ai_thinking = False
        self._ai_result = None
        self._ai_thread = None
        self._ai_move_display_timer = 0
        self._ai_needs_confirm = False
        self._ai_display_phase = 0
        self._ai_pending_moves.clear()

    def ai_tick(self) -> bool:
        """
        AI 逐帧调用。实现分阶段显示：
          阶段1: 等待1秒后显示第1颗AI落子
          阶段2: 等待1秒后显示第2颗AI落子
          阶段3: 短暂停顿后确认落子并切换回合
        返回 True 表示执行了某操作，False 表示空闲。
        """
        if not self.is_ai_turn():
            return False
        if self._ai is None:
            return False

        # ===== 阶段 0: 启动 AI 计算 =====
        if self._ai_display_phase == 0 and not self._ai_thinking and self._ai_result is None:
            self._start_ai_thinking()
            return True

        # ===== AI 计算完成 → 进入阶段 1 =====
        if self._ai_display_phase == 0 and not self._ai_thinking and self._ai_result is not None:
            moves = self._ai_result
            self._ai_result = None
            if moves and len(moves) > 0:
                self._ai_pending_moves = list(moves)
                # 进入阶段1：等待0.33秒显示第一颗子
                self._ai_display_phase = 1
                self._ai_move_display_timer = 10  # FPS=30, ~10帧后开始倒计时
                return True
            else:
                return False

        # ===== 阶段 1: 等待显示第一颗AI落子 =====
        if self._ai_display_phase == 1:
            if self._ai_move_display_timer > 0:
                self._ai_move_display_timer -= 1
                return False
            # 时间到：落第一颗子
            if len(self._ai_pending_moves) > 0:
                r, c = self._ai_pending_moves[0]
                self.place_stone(r, c)
                self._ai_display_phase = 2
                self._ai_move_display_timer = 15  # 0.5秒 (15帧)
                return True

        # ===== 阶段 2: 显示第一颗子后等待0.5秒 =====
        if self._ai_display_phase == 2:
            if self._ai_move_display_timer > 0:
                self._ai_move_display_timer -= 1
                return False
            # 时间到：落第二颗子
            if len(self._ai_pending_moves) > 1:
                r, c = self._ai_pending_moves[1]
                self.place_stone(r, c)
                self._ai_display_phase = 3
                self._ai_move_display_timer = 10  # 0.33秒 (10帧)
                return True
            else:
                # 只有1颗子（第一手特殊情况？不会出现，但健壮处理）
                self._ai_display_phase = 4
                self._ai_move_display_timer = 10
                return True

        # ===== 阶段 3: 显示第二颗子后等待0.33秒 =====
        if self._ai_display_phase == 3:
            if self._ai_move_display_timer > 0:
                self._ai_move_display_timer -= 1
                return False
            # 时间到：进入确认阶段
            self._ai_display_phase = 4
            self._ai_move_display_timer = 5  # 0.16秒短暂停顿
            return True

        # ===== 阶段 4: 短暂停顿后确认落子 =====
        if self._ai_display_phase == 4:
            if self._ai_move_display_timer > 0:
                self._ai_move_display_timer -= 1
                return False
            won = self.confirm_move()
            self._ai_display_phase = 0
            self._ai_pending_moves.clear()
            return True

        return False
