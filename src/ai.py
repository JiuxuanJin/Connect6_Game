"""
connect6 AI 引擎
Minimax + Alpha-Beta 剪枝
支持执黑或执白，支持三种难度
"""

from __future__ import annotations
import math
import random
from collections import Counter
from .config import (
    BOARD_SIZE, EMPTY, BLACK, WHITE,
    AI_BLACK_FIRST_MOVE_WEIGHTS, STAR_POINTS,
)
from .board import Board
from .evaluate import (
    evaluate, score_position, clear_eval_cache, DIRECTIONS,
    find_winning_moves, find_winning_pairs,
)

# Minimax 默认搜索深度（会被难度覆盖）
SEARCH_DEPTH = 1

# 候选着法单点数量上限
MAX_SINGLE_CANDIDATES = 12

# 候选着法对数量上限（2 子一轮时）
MAX_PAIR_CANDIDATES = 50

# 候选点搜索范围：仅考虑距离已有棋子 3 格以内的空位
CANDIDATE_RADIUS = 3


class AIPlayer:
    """六子棋 AI 玩家（可执黑或执白）"""

    def __init__(self, player_color: int = WHITE, search_depth: int = 1,
                 enable_force_win_detection: bool = False, ad_v: float = 1.0,
                 enable_multi_threat: bool = False):
        """
        player_color: AI 执子颜色 (BLACK 或 WHITE)
        search_depth: minimax 搜索深度 (1, 2, 3)
        enable_force_win_detection: 是否启用必胜手检测
        ad_v: 攻防倾向，0=纯防守，2=纯进攻，1=均衡
        enable_multi_threat: 是否启用多重威胁检测
        """
        self.player = player_color
        self.opponent = BLACK if player_color == WHITE else WHITE
        self.depth = search_depth
        self._check_wins = enable_force_win_detection
        self.ad_v = ad_v
        self._enable_multi_threat = enable_multi_threat
        self._nodes_searched = 0

    def get_first_move_as_black(self) -> list[tuple[int, int]]:
        """
        AI 执黑第一步：按权重从9个星位中随机选择。
        天元(9,9)权重0.44，其余8个星位各0.07。
        返回包含单个位置的列表。
        """
        positions = list(AI_BLACK_FIRST_MOVE_WEIGHTS.keys())
        weights = list(AI_BLACK_FIRST_MOVE_WEIGHTS.values())
        # 使用 random.choices 按权重选择
        chosen = random.choices(positions, weights=weights, k=1)[0]
        return [chosen]

    def get_move(self, board: Board, stones_to_place: int) -> list[tuple[int, int]]:
        """
        计算并返回 AI 本轮应落子的位置列表。

        策略优先级（行家/宗师）：
        1. AI 自己有必杀 → 直接落必胜子，跳过后续搜索
        2. 对手有必杀 → 逐颗尝试堵，威胁消失即停止堵子
        3. 剩子 → minimax 搜索

        新秀难度：跳过必杀判定，直接 minimax 搜索。
        """
        self._nodes_searched = 0
        clear_eval_cache()
        player = self.player
        opponent = self.opponent

        # ---- 阶段 1：AI 自己的必胜 ────
        if self._check_wins:
            own_wins = self._find_own_wins(board, player)
            if own_wins:
                return own_wins[:stones_to_place]

        # ---- 阶段 2：堵对手威胁（逐颗验证） ────
        if self._check_wins:
            block_moves = self._block_threats_iteratively(board, opponent, player, stones_to_place)
        else:
            block_moves = []

        remaining = stones_to_place - len(block_moves)

        if remaining <= 0:
            return block_moves[:stones_to_place]

        # ---- 阶段 3：Minimax ────
        for r, c in block_moves:
            board.place_stone(r, c, player)

        extra = self._search_remaining(board, player, remaining)

        for r, c in reversed(block_moves):
            board.remove_stone(r, c)

        result = block_moves + extra
        if len(result) < stones_to_place:
            result = result + self._fallback_moves(board, stones_to_place - len(result))
        return result[:stones_to_place]

    def _find_own_wins(self, board: Board, player: int) -> list[tuple[int, int]]:
        """
        找出 AI 自己的必杀落子。
        包括：一步致胜（5 连缺 1）和双步致胜（4 连缺 2）。
        优先处理跳模式（落中间空位）。返回应立即落子的位置列表。
        """
        # 一步致胜：已有 5 连缺 1 子
        winning_moves = find_winning_moves(board, player)
        if winning_moves:
            return winning_moves[:2]

        # 双子致胜：已有 4 连缺 2 子
        winning_pairs = find_winning_pairs(board, player)
        if winning_pairs:
            # 选一个必胜对，从中找最优先手（优先落"跳"的中间空位）
            best = self._pick_best_pair_to_complete(board, player, winning_pairs)
            return list(best)

        return []

    def _block_threats_iteratively(
        self, board: Board, opponent: int, player: int, max_blocks: int
    ) -> list[tuple[int, int]]:
        """
        逐颗尝试堵对手威胁。
        每次落一颗堵子后重新检测，威胁消失则停止，剩余子留给 minimax。
        返回模拟落过的堵子位置列表（棋盘上已模拟放置，调用方负责撤回）。
        """
        blocks: list[tuple[int, int]] = []

        for _ in range(max_blocks):
            # 先查一步致胜
            one_steps = find_winning_moves(board, opponent)
            if one_steps:
                # 对手 5 连缺 1 → 必须堵该空位
                block = one_steps[0]
                if not board.is_empty(block[0], block[1]):
                    # 已被之前的堵子占住，威胁已消
                    continue
                blocks.append(block)
                board.place_stone(block[0], block[1], player)
                continue

            # 再查双子致胜
            pairs = find_winning_pairs(board, opponent)
            if not pairs:
                # 无威胁，停止堵
                break

            # 从所有威胁对中选最优堵点
            block = self._best_block_position(board, opponent, pairs)
            blocks.append(block)
            board.place_stone(block[0], block[1], player)

        # 撤回所有模拟堵子（让 _get_move 调用方统一处理）
        for r, c in reversed(blocks):
            board.remove_stone(r, c)

        return blocks

    def _best_block_position(
        self,
        board: Board,
        opponent: int,
        pairs: list[tuple[tuple[int, int], tuple[int, int]]],
    ) -> tuple[int, int]:
        """
        从所有威胁对中选出最优的单个堵点。
        策略：
        1. 优先堵"跳"模式的中间空位（一子破双威胁）
        2. 其次堵出现频率最高的空位
        3. 对同一对内的两个空位，优先堵与棋子簇相邻更近的
        """
        # 第一优先级：检测 gap（跳模式中间空位）
        gap_candidates = self._find_gap_positions(board, opponent, pairs)
        if gap_candidates:
            # 选出现次数最多的 gap
            gap_freq = Counter(gap_candidates)
            best_gap = gap_freq.most_common(1)[0][0]
            return best_gap

        # 第二优先级：频率贪心（堵出现次数最多的空位）
        freq = Counter()
        for (r1, c1), (r2, c2) in pairs:
            # 对每个位置加权：越靠近棋子簇权重越高
            freq[(r1, c1)] += self._position_block_weight(board, r1, c1, opponent)
            freq[(r2, c2)] += self._position_block_weight(board, r2, c2, opponent)

        best = freq.most_common(1)[0][0]
        return best

    def _find_gap_positions(
        self,
        board: Board,
        opponent: int,
        pairs: list[tuple[tuple[int, int], tuple[int, int]]],
    ) -> list[tuple[int, int]]:
        """
        找出所有威胁对中的"跳"模式中间空位（gap）。
        gap 的定义：空位的两侧（沿威胁方向）都有 opponent 的棋子。
        即该空位是夹在对方棋子之间的空格。

        返回所有 gap 位置的列表（可能重复，调用方用 Counter 统计频率）。
        """
        gaps: list[tuple[int, int]] = []
        size = board.size
        grid = board.grid

        for (r1, c1), (r2, c2) in pairs:
            for r, c in ((r1, c1), (r2, c2)):
                if grid[r][c] != EMPTY:
                    continue
                # 检查四个方向，看是否有两侧都有 opponent 棋子（或一端是 opponent + 另一端将也是 opponent 的空位）
                for dr, dc in DIRECTIONS:
                    # 正方向找 opponent
                    rr, cc = r + dr, c + dc
                    has_opp_plus = False
                    while 0 <= rr < size and 0 <= cc < size:
                        if grid[rr][cc] == opponent:
                            has_opp_plus = True
                            break
                        elif grid[rr][cc] != EMPTY:
                            break
                        rr += dr
                        cc += dc
                    # 反方向找 opponent
                    rr, cc = r - dr, c - dc
                    has_opp_minus = False
                    while 0 <= rr < size and 0 <= cc < size:
                        if grid[rr][cc] == opponent:
                            has_opp_minus = True
                            break
                        elif grid[rr][cc] != EMPTY:
                            break
                        rr -= dr
                        cc -= dc
                    if has_opp_plus and has_opp_minus:
                        gaps.append((r, c))
                        break  # 该位置在某方向上已是 gap，无需检查其他方向

        return gaps

    def _position_block_weight(self, board: Board, r: int, c: int, opponent: int) -> float:
        """
        计算某个堵位的权重。权重越高越优先堵。
        与对手棋子相邻的空位权重更高（因为堵近端比堵远端更有效）。
        """
        size = board.size
        grid = board.grid
        weight = 1.0

        for dr, dc in DIRECTIONS:
            rr, cc = r + dr, c + dc
            if 0 <= rr < size and 0 <= cc < size and grid[rr][cc] == opponent:
                weight += 2.0  # 紧邻对手棋子，权重翻倍
            rr, cc = r - dr, c - dc
            if 0 <= rr < size and 0 <= cc < size and grid[rr][cc] == opponent:
                weight += 2.0

        return weight

    def _pick_best_pair_to_complete(
        self,
        board: Board,
        player: int,
        pairs: list[tuple[tuple[int, int], tuple[int, int]]],
    ) -> tuple[tuple[int, int], tuple[int, int]]:
        """
        从多个必胜对中，选一个最优的来落子完成。
        优先选有"跳"模式的（先落中间空位，后落边位）。
        返回排序好的 ((first_r, first_c), (second_r, second_c))，先落最有价值的子。
        """
        best_pair = None
        best_score = -1

        for (r1, c1), (r2, c2) in pairs:
            # 打分：看这个对的两个位置是否包含 gap
            score = 0
            # 简化：使用 _find_gap_positions 逻辑检查
            is_gap_1 = self._is_gap(board, r1, c1, player)
            is_gap_2 = self._is_gap(board, r2, c2, player)
            if is_gap_1:
                score += 10
            if is_gap_2:
                score += 10
            # 加距离中心奖励
            score += (9 - abs(r1 - 9)) * 0.1 + (9 - abs(c1 - 9)) * 0.1
            score += (9 - abs(r2 - 9)) * 0.1 + (9 - abs(c2 - 9)) * 0.1

            if score > best_score:
                best_score = score
                # gap 优先落
                if is_gap_1 and not is_gap_2:
                    best_pair = ((r1, c1), (r2, c2))
                elif is_gap_2 and not is_gap_1:
                    best_pair = ((r2, c2), (r1, c1))
                else:
                    best_pair = ((r1, c1), (r2, c2))

        if best_pair is None:
            return pairs[0]
        return best_pair

    def _is_gap(self, board: Board, r: int, c: int, player: int) -> bool:
        """检查空位 (r,c) 在某方向上两侧都有 player 棋子（即为跳模式的空隙）"""
        size = board.size
        grid = board.grid
        if grid[r][c] != EMPTY:
            return False

        for dr, dc in DIRECTIONS:
            has_plus = False
            rr, cc = r + dr, c + dc
            while 0 <= rr < size and 0 <= cc < size:
                if grid[rr][cc] == player:
                    has_plus = True
                    break
                elif grid[rr][cc] != EMPTY:
                    break
                rr += dr
                cc += dc

            has_minus = False
            rr, cc = r - dr, c - dc
            while 0 <= rr < size and 0 <= cc < size:
                if grid[rr][cc] == player:
                    has_minus = True
                    break
                elif grid[rr][cc] != EMPTY:
                    break
                rr -= dr
                cc -= dc

            if has_plus and has_minus:
                return True
        return False

    def _search_remaining(
        self, board: Board, player: int, stones_to_place: int
    ) -> list[tuple[int, int]]:
        """在已模拟部分落子后，用 minimax 搜索剩余落子"""
        if stones_to_place == 1:
            return self._search_single(board, player)
        else:
            return self._search_pair(board, player)

    def _search_single(self, board: Board, player: int) -> list[tuple[int, int]]:
        """单子搜索：直接对候选单点做 minimax"""
        candidates = self._get_single_candidates(board, player, top_n=MAX_SINGLE_CANDIDATES)

        best_move = None
        best_score = -math.inf
        alpha = -math.inf
        beta = math.inf

        # 带随机打乱避免重复选择同一候选
        random.shuffle(candidates)

        for move in candidates:
            r, c = move
            board.place_stone(r, c, player)
            # 检查是否直接获胜
            if board.check_win(r, c):
                board.remove_stone(r, c)
                return [move]

            # 切换到对方回合（对方需要落 2 子）
            score = self._minimax(
                board, 1, -math.inf, math.inf, WHITE if player == BLACK else BLACK, 2
            )
            board.remove_stone(r, c)

            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, best_score)

        if best_move is None:
            return []
        return [best_move]

    def _search_pair(self, board: Board, player: int) -> list[tuple[int, int]]:
        """双子搜索：从候选单点生成对组合做 minimax"""
        singles = self._get_single_candidates(board, player, top_n=MAX_SINGLE_CANDIDATES)
        if len(singles) < 2:
            # 不足2个候选，用随机兜底
            return self._fallback_moves(board, 2)

        # 生成对组合
        pairs = []
        n = len(singles)
        for i in range(n):
            for j in range(i + 1, n):
                pairs.append((singles[i], singles[j]))

        # 限制数量
        if len(pairs) > MAX_PAIR_CANDIDATES:
            # 按两个点各自 score 之和排序，取前 MAX_PAIR_CANDIDATES 个
            scored_pairs = []
            for (r1, c1), (r2, c2) in pairs:
                s = score_position(board, r1, c1, player, self.ad_v, self._enable_multi_threat) + score_position(board, r2, c2, player, self.ad_v, self._enable_multi_threat)
                scored_pairs.append(((r1, c1, r2, c2), s))
            scored_pairs.sort(key=lambda x: x[1], reverse=True)
            pairs = [((r1, c1), (r2, c2)) for (r1, c1, r2, c2), _ in scored_pairs[:MAX_PAIR_CANDIDATES]]

        best_pair = None
        best_score = -math.inf
        alpha = -math.inf
        beta = math.inf

        random.shuffle(pairs)

        for (r1, c1), (r2, c2) in pairs:
            # 模拟落 2 子
            board.place_stone(r1, c1, player)
            board.place_stone(r2, c2, player)

            # 检查获胜
            win = board.check_win(r1, c1) or board.check_win(r2, c2)

            if win:
                board.remove_stone(r2, c2)
                board.remove_stone(r1, c1)
                return [(r1, c1), (r2, c2)]

            # 切换到对方
            opponent = WHITE if player == BLACK else BLACK
            score = self._minimax(board, 1, -math.inf, math.inf, opponent, 2)

            board.remove_stone(r2, c2)
            board.remove_stone(r1, c1)

            if score > best_score:
                best_score = score
                best_pair = ((r1, c1), (r2, c2))
            alpha = max(alpha, best_score)

        if best_pair is None:
            return self._fallback_moves(board, 2)
        return list(best_pair)

    def _minimax(
        self,
        board: Board,
        depth: int,
        alpha: float,
        beta: float,
        current_player: int,
        stones_to_place: int,
    ) -> float:
        """
        Minimax + Alpha-Beta 搜索。
        每层代表一个玩家的一轮完整行动（落 stones_to_place 子）。
        depth=0 时评估局面。
        """
        if depth >= self.depth:
            # 到达深度上限，从 AI 视角评估
            return evaluate(board, self.player)

        # 尚未实现本轮落子
        # 生成候选着法
        if stones_to_place == 1:
            return self._minimax_single(board, depth, alpha, beta, current_player)
        else:
            return self._minimax_pair(board, depth, alpha, beta, current_player, stones_to_place)

    def _minimax_single(
        self,
        board: Board,
        depth: int,
        alpha: float,
        beta: float,
        current_player: int,
    ) -> float:
        """单子 minimax 分支"""
        candidates = self._get_single_candidates(board, current_player, top_n=MAX_SINGLE_CANDIDATES)
        opponent = WHITE if current_player == BLACK else BLACK
        # 对方下一轮都是落 2 子
        next_stones = 2

        is_maximizing = (current_player == self.player)  # AI 执棋色

        if is_maximizing:
            value = -math.inf
            for r, c in candidates:
                board.place_stone(r, c, current_player)
                if board.check_win(r, c):
                    board.remove_stone(r, c)
                    return 1_000_000  # AI 获胜
                child_val = self._minimax(board, depth + 1, alpha, beta, opponent, next_stones)
                board.remove_stone(r, c)
                value = max(value, child_val)
                if value >= beta:
                    break
                alpha = max(alpha, value)
            return value
        else:
            value = math.inf
            for r, c in candidates:
                board.place_stone(r, c, current_player)
                if board.check_win(r, c):
                    board.remove_stone(r, c)
                    return -1_000_000  # 对手获胜
                child_val = self._minimax(board, depth + 1, alpha, beta, opponent, next_stones)
                board.remove_stone(r, c)
                value = min(value, child_val)
                if value <= alpha:
                    break
                beta = min(beta, value)
            return value

    def _minimax_pair(
        self,
        board: Board,
        depth: int,
        alpha: float,
        beta: float,
        current_player: int,
        stones_to_place: int,
    ) -> float:
        """双子 minimax 分支"""
        singles = self._get_single_candidates(board, current_player, top_n=MAX_SINGLE_CANDIDATES)
        if len(singles) < 2:
            # 不够候选，回退评估
            return evaluate(board, self.player)

        # 生成对组合
        pairs = []
        n = len(singles)
        for i in range(n):
            for j in range(i + 1, n):
                pairs.append((singles[i], singles[j]))

        # 限制数量并排序
        if len(pairs) > MAX_PAIR_CANDIDATES:
            scored = []
            for (r1, c1), (r2, c2) in pairs:
                s = score_position(board, r1, c1, current_player, self.ad_v, self._enable_multi_threat) + score_position(board, r2, c2, current_player, self.ad_v, self._enable_multi_threat)
                scored.append(((r1, c1, r2, c2), s))
            scored.sort(key=lambda x: x[1], reverse=True)
            pairs = [((r1, c1), (r2, c2)) for (r1, c1, r2, c2), _ in scored[:MAX_PAIR_CANDIDATES]]

        opponent = WHITE if current_player == BLACK else BLACK
        # 对方下一轮都是落 2 子
        next_stones = 2
        is_maximizing = (current_player == self.player)

        if is_maximizing:
            value = -math.inf
            for (r1, c1), (r2, c2) in pairs:
                board.place_stone(r1, c1, current_player)
                board.place_stone(r2, c2, current_player)
                win = board.check_win(r1, c1) or board.check_win(r2, c2)
                if win:
                    board.remove_stone(r2, c2)
                    board.remove_stone(r1, c1)
                    return 1_000_000
                child_val = self._minimax(board, depth + 1, alpha, beta, opponent, next_stones)
                board.remove_stone(r2, c2)
                board.remove_stone(r1, c1)
                value = max(value, child_val)
                if value >= beta:
                    break
                alpha = max(alpha, value)
            return value
        else:
            value = math.inf
            for (r1, c1), (r2, c2) in pairs:
                board.place_stone(r1, c1, current_player)
                board.place_stone(r2, c2, current_player)
                win = board.check_win(r1, c1) or board.check_win(r2, c2)
                if win:
                    board.remove_stone(r2, c2)
                    board.remove_stone(r1, c1)
                    return -1_000_000
                child_val = self._minimax(board, depth + 1, alpha, beta, opponent, next_stones)
                board.remove_stone(r2, c2)
                board.remove_stone(r1, c1)
                value = min(value, child_val)
                if value <= alpha:
                    break
                beta = min(beta, value)
            return value

    def _get_single_candidates(
        self, board: Board, player: int, top_n: int = MAX_SINGLE_CANDIDATES
    ) -> list[tuple[int, int]]:
        """获取前 top_n 个候选单点，仅考虑距离已有棋子 CANDIDATE_RADIUS 格以内的空位"""
        # 先收集所有已有棋子位置
        stones = [
            (r, c)
            for r in range(BOARD_SIZE)
            for c in range(BOARD_SIZE)
            if board.get_cell(r, c) != EMPTY
        ]

        if not stones:
            # 空棋盘：随机选中心附近
            cx = cy = BOARD_SIZE // 2
            return [(cx, cy)]

        # 收集距离已有棋子 CANDIDATE_RADIUS 格以内的空位（去重）
        nearby_empty = set()
        for sr, sc in stones:
            r_min = max(0, sr - CANDIDATE_RADIUS)
            r_max = min(BOARD_SIZE, sr + CANDIDATE_RADIUS + 1)
            c_min = max(0, sc - CANDIDATE_RADIUS)
            c_max = min(BOARD_SIZE, sc + CANDIDATE_RADIUS + 1)
            for r in range(r_min, r_max):
                for c in range(c_min, c_max):
                    if board.is_empty(r, c):
                        nearby_empty.add((r, c))

        if not nearby_empty:
            # 兜底：遍历全部空位
            nearby_empty = set(
                (r, c)
                for r in range(BOARD_SIZE)
                for c in range(BOARD_SIZE)
                if board.is_empty(r, c)
            )

        scored = []
        for r, c in nearby_empty:
            s = score_position(board, r, c, player, self.ad_v, self._enable_multi_threat)
            if s > 0:
                scored.append(((r, c), s))

        scored.sort(key=lambda x: x[1], reverse=True)

        # 如果候选太少，扩大半径再搜
        if len(scored) < top_n:
            existing = {pos for pos, _ in scored}
            # 扩大搜索：全部空位中选最近的
            extra = []
            for r in range(BOARD_SIZE):
                for c in range(BOARD_SIZE):
                    if (r, c) in existing:
                        continue
                    if board.is_empty(r, c):
                        dist = self._min_distance_to_stone(board, r, c)
                        extra.append(((r, c), -dist))
            extra.sort(key=lambda x: x[1], reverse=True)
            for pos, s in extra:
                if len(scored) >= top_n:
                    break
                if pos not in existing:
                    scored.append((pos, s))

        result = [pos for pos, _ in scored[:top_n]]
        return result

    def _min_distance_to_stone(self, board: Board, r: int, c: int) -> int:
        """计算 (r, c) 到最近已有棋子的曼哈顿距离"""
        min_dist = BOARD_SIZE * 2
        for rr in range(max(0, r - 5), min(BOARD_SIZE, r + 6)):
            for cc in range(max(0, c - 5), min(BOARD_SIZE, c + 6)):
                if board.get_cell(rr, cc) != EMPTY:
                    dist = abs(r - rr) + abs(c - cc)
                    if dist < min_dist:
                        min_dist = dist
        return min_dist

    def _fallback_moves(self, board: Board, count: int) -> list[tuple[int, int]]:
        """兜底：随机选取空位"""
        empties = [
            (r, c)
            for r in range(BOARD_SIZE)
            for c in range(BOARD_SIZE)
            if board.is_empty(r, c)
        ]
        random.shuffle(empties)
        return empties[:count]