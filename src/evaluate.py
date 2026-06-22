"""
connect6 局面评估模块
活、冲、跳三种模式独立评分
"""

from .config import BOARD_SIZE, EMPTY, BLACK, WHITE

# =====================================================================
# 独立模式评分表
# =====================================================================

# ── 活 (Live)：两端都开放，连续无空 ──
# 例：_XXX_ 是活三，_XXXX_ 是活四
LIVE_WEIGHTS = {
    1: 10,
    2: 100,
    3: 1000,
    4: 10000,
    5: 50000,
    6: 100000000,
}

# ── 冲 (Rush)：一端开放，一端被堵，连续无空 ──
# 例：#XXX_ 是冲三，_XXXX# 是冲四
RUSH_WEIGHTS = {
    1: 5,
    2: 70,
    3: 700,
    4: 6000,
    5: 30000,
    6: 100000000,
}

# ── 跳活 (Jump Live)：两端开放，中间有一个空位 ──
# 例：_XX_X_ 是跳活三，_X_XXX_ 是跳活四
JUMP_LIVE_WEIGHTS = {
    2: 80,     # _X_X_
    3: 800,    # _XX_X_ 或 _X_XX_
    4: 7000,   # _XXX_X_ 或 _XX_XX_
    5: 35000,  # _XXXX_X_ 或 _XXX_XX_
    6: 100000,
}

# ── 跳冲 (Jump Rush)：一端开放，中间有一个空位 ──
# 例：#XX_X_ 是跳冲三
JUMP_RUSH_WEIGHTS = {
    2: 50,     # #X_X_ 或 _X_X#
    3: 500,    # #XX_X_ 或 _XX_X#
    4: 5500,   # #XXX_X_ 或 _XXX_X#
    5: 28000,  # #XXXX_X_ 或 _XXXX_X#
    6: 100000,
}

# 各模式类型到权重表的映射
PATTERN_SCORE_TABLE = {
    'live':      LIVE_WEIGHTS,
    'rush':      RUSH_WEIGHTS,
    'jump_live': JUMP_LIVE_WEIGHTS,
    'jump_rush': JUMP_RUSH_WEIGHTS,
}


def _get_pattern_score(pattern_type: str, n: int) -> float:
    """根据模式类型和连子数获取分值"""
    table = PATTERN_SCORE_TABLE.get(pattern_type, {})
    return table.get(n, 0)


# =====================================================================
# 缓存
# =====================================================================

_eval_cache: dict[tuple, float] = {}
_score_cache: dict[tuple, float] = {}


def clear_eval_cache():
    """清除所有评估缓存（每轮 AI 搜索前调用）"""
    _eval_cache.clear()
    _score_cache.clear()


# =====================================================================
# 位置奖励
# =====================================================================

CENTER = (BOARD_SIZE - 1) / 2


def _position_bonus(r: int, c: int) -> float:
    """位置奖励：越靠近中心分数越高（边角惩罚最多 30%）"""
    dr = r - CENTER
    dc = c - CENTER
    dist = abs(dr) + abs(dc)
    max_dist = BOARD_SIZE * 2
    return 1.0 - (dist / max_dist) * 0.3


# =====================================================================
# 方向定义
# =====================================================================

DIRECTIONS = [
    (0, 1),   # 水平
    (1, 0),   # 垂直
    (1, 1),   # 对角线 ↘
    (1, -1),  # 对角线 ↙
]


# =====================================================================
# 单方向模式分析（核心）
# =====================================================================

def _analyze_direction_placing(
    board,
    r: int,
    c: int,
    dr: int,
    dc: int,
    player: int,
) -> float:
    """
    分析：假设在 (r,c) 放置 player 色棋子后，沿 (dr,dc) 方向形成的模式。
    返回该方向的总评分。

    扫描算法：
      以 (r,c) 为中心，向正方向和反方向各扩展最多 L-1 步（L=6 为获胜长度）。
      统计跨度内的同色棋子数、空位数、两端开放状态，从而判断模式类型。

    模式分类规则：
      - 空位 = 0 且两端开放 = 活
      - 空位 = 0 且一端开放 = 冲
      - 空位 = 1 且两端开放 = 跳活
      - 空位 = 1 且一端开放 = 跳冲
      - 否则 = 死（不计分）
    """
    WIN_LEN = 6
    grid = board.grid
    size = board.size

    # ---- 扫描正方向 ----
    stones_pos = 0  # 正方向连续/跳连棋子数
    gaps_pos = 0    # 正方向空位数
    open_pos = True

    rr, cc = r + dr, c + dc
    seen_gap = False
    for _ in range(WIN_LEN - 1):  # 除 (r,c) 自身外最多再查 5 格
        if not (0 <= rr < size and 0 <= cc < size):
            open_pos = False
            break
        cell = grid[rr][cc]
        if cell == player:
            if seen_gap:
                gaps_pos += 1  # 之前跳过的那个空位算 gap
                seen_gap = False
            stones_pos += 1
        elif cell == EMPTY:
            if stones_pos == 0 and gaps_pos == 0:
                # 开头就是空位 → 开放端就是这里
                break
            # 已经见到棋子后遇到空位 → 可能是跳
            if seen_gap:
                # 已经有一个 gap 了，再来一个空位 → 结束
                break
            # 记录跳的空位，继续往后看
            seen_gap = True
            rr += dr
            cc += dc
            continue
        else:
            # 遇到对方棋子 → 堵死
            open_pos = False
            break
        rr += dr
        cc += dc

    # 如果循环结束时 seen_gap 仍为 True，说明最后一个位置是空位→计入 gaps
    # 实际上 seen_gap 表示"上一个位置是空位且我们跳过了它"，此时再遇到棋子才会 flush
    # 如果扫描完还没 flush，说明这个 gap 后面没有棋子→不构成跳模式→gaps_pos > 0 返回时会被正确分类

    # ---- 扫描反方向 ----
    stones_neg = 0
    gaps_neg = 0
    open_neg = True

    rr, cc = r - dr, c - dc
    seen_gap = False
    for _ in range(WIN_LEN - 1):
        if not (0 <= rr < size and 0 <= cc < size):
            open_neg = False
            break
        cell = grid[rr][cc]
        if cell == player:
            if seen_gap:
                gaps_neg += 1
                seen_gap = False
            stones_neg += 1
        elif cell == EMPTY:
            if stones_neg == 0 and gaps_neg == 0:
                break
            if seen_gap:
                break
            seen_gap = True
            rr += dr  # 注意：反方向继续移动是减去 dc，但这里循环变量已经处理了
            cc += dc
            continue
        else:
            open_neg = False
            break
        rr -= dr
        cc -= dc

    # ---- 汇总 ----
    total_stones = stones_pos + stones_neg + 1  # +1 = (r,c) 自身
    total_gaps = gaps_pos + gaps_neg
    open_ends = (1 if open_pos else 0) + (1 if open_neg else 0)

    # ---- 分类打分 ----
    if total_gaps == 0:
        if open_ends == 2:
            return _get_pattern_score('live', min(total_stones, 6))
        elif open_ends == 1:
            return _get_pattern_score('rush', min(total_stones, 6))
        else:
            # 两端都堵死 → 极低分
            return _get_pattern_score('rush', min(total_stones, 6)) * 0.1
    elif total_gaps == 1:
        if open_ends == 2:
            return _get_pattern_score('jump_live', min(total_stones, 6))
        elif open_ends == 1:
            return _get_pattern_score('jump_rush', min(total_stones, 6))
        else:
            return _get_pattern_score('jump_rush', min(total_stones, 6)) * 0.1
    else:
        # 多空位 → 忽略
        return 0.0


# =====================================================================
# 候选着法评分（用于 AI 排序）
# =====================================================================

def score_position(board, r: int, c: int, player: int, ad_v: float = 1.0,
                   enable_multi_threat: bool = False) -> float:
    """
    评估在 (r,c) 落 player 色棋子的启发式分数。
    计算该位置在四个方向上形成的攻防模式总分。
    仅用于排序候选着法。
    ad_v: 攻防倾向，0=纯防守，2=纯进攻，1=均衡
    enable_multi_threat: 若为 True，当多个方向均出现高威胁评分时，
                         攻击/防御总分将获得额外加权。
    """
    if not board.is_empty(r, c):
        return -1.0

    grid_tuple = _board_to_tuple(board)
    cache_key = (grid_tuple, r, c, player, ad_v, enable_multi_threat)
    if cache_key in _score_cache:
        return _score_cache[cache_key]

    attack = 0.0
    defense = 0.0
    opponent = WHITE if player == BLACK else BLACK

    # 多重威胁检测：统计单方向评分 > 999 的方向数
    high_atk_dirs = 0
    high_def_dirs = 0

    for dr, dc in DIRECTIONS:
        atk_dir = _analyze_direction_placing(board, r, c, dr, dc, player)
        def_dir = _analyze_direction_placing(board, r, c, dr, dc, opponent)
        attack += atk_dir
        defense += def_dir
        if atk_dir > 999:
            high_atk_dirs += 1
        if def_dir > 999:
            high_def_dirs += 1

    # 多重威胁增益：>1 个方向同时有高威胁 → 额外加权
    if enable_multi_threat:
        if high_atk_dirs > 1:
            attack *= 3.0
        if high_def_dirs > 1:
            defense *= 3.0

    # 攻防加权：ad_v=0防御权重2，ad_v=1均衡各1，ad_v=2进攻权重2
    score = attack * ad_v + defense * (2 - ad_v)
    score *= _position_bonus(r, c)

    _score_cache[cache_key] = score
    return score


# =====================================================================
# 棋盘整体评估
# =====================================================================

def _board_to_tuple(board) -> tuple:
    """将棋盘转换为不可变元组用于缓存键"""
    return tuple(tuple(row) for row in board.grid)


def evaluate(board, player: int) -> float:
    """
    从 player 视角评估整个棋盘的局势分数。
    正值 = player 有利，负值 = 对手有利。

    扫描棋盘上每颗已有棋子，在其所在直线的"起点"处计算模式分值，
    避免从线段中间重复计数。
    """
    grid_tuple = _board_to_tuple(board)
    cache_key = (grid_tuple, player)
    if cache_key in _eval_cache:
        return _eval_cache[cache_key]

    total = 0.0
    opponent = WHITE if player == BLACK else BLACK
    grid = board.grid
    size = board.size

    for r in range(size):
        for c in range(size):
            stone = grid[r][c]
            if stone == EMPTY:
                continue
            # 确定符号
            sign = 1.0 if stone == player else -1.0

            for dr, dc in DIRECTIONS:
                # 只从线段起点开始扫描，避免重复
                pr, pc = r - dr, c - dc
                if 0 <= pr < size and 0 <= pc < size and grid[pr][pc] == stone:
                    continue  # 上一格同色 → 不是起点 → 跳过

                # 从该起点沿正方向扫描
                line_score = _analyze_existing_line(board, r, c, dr, dc, stone)
                total += sign * line_score

    _eval_cache[cache_key] = total
    return total


def _analyze_existing_line(
    board,
    r: int,
    c: int,
    dr: int,
    dc: int,
    player: int,
) -> float:
    """
    从已有棋子的线段起点 (r,c) 沿 (dr,dc) 方向分析该线段模式。

    与 _analyze_direction_placing 不同，这里 (r,c) 已落有 player 色棋子，
    且保证 (r-dr, c-dc) 不是同色（即为线段起点）。
    """
    WIN_LEN = 6
    grid = board.grid
    size = board.size

    # 起点外侧
    pr, pc = r - dr, c - dc
    if not (0 <= pr < size and 0 <= pc < size):
        open_start = False
    elif grid[pr][pc] != EMPTY:
        open_start = False
    else:
        open_start = True

    # 正方向扫描
    stones = 1  # 包含 (r,c) 自身
    gaps = 0
    open_end = True

    rr, cc = r + dr, c + dc
    seen_gap = False
    for _ in range(WIN_LEN - 1):
        if not (0 <= rr < size and 0 <= cc < size):
            open_end = False
            break
        cell = grid[rr][cc]
        if cell == player:
            if seen_gap:
                gaps += 1
                seen_gap = False
            stones += 1
        elif cell == EMPTY:
            if seen_gap:
                break
            seen_gap = True
            rr += dr
            cc += dc
            continue
        else:
            open_end = False
            break
        rr += dr
        cc += dc

    open_ends = (1 if open_start else 0) + (1 if open_end else 0)

    # ---- 分类打分 ----
    if gaps == 0:
        if open_ends == 2:
            return _get_pattern_score('live', min(stones, 6))
        elif open_ends == 1:
            return _get_pattern_score('rush', min(stones, 6))
        else:
            return _get_pattern_score('rush', min(stones, 6)) * 0.1
    elif gaps == 1:
        if open_ends == 2:
            return _get_pattern_score('jump_live', min(stones, 6))
        elif open_ends == 1:
            return _get_pattern_score('jump_rush', min(stones, 6))
        else:
            return _get_pattern_score('jump_rush', min(stones, 6)) * 0.1
    else:
        return 0.0


# =====================================================================
# 必胜威胁检测（用于 AI 在 Minimax 之前的策略判断）
# =====================================================================

def find_winning_moves(board, player: int) -> list[tuple[int, int]]:
    """
    找出所有"一步致胜"的落子位置。
    即：在该空位放置 player 色棋子后，立即形成六连。
    返回 [(r,c), ...] 列表（去重）。
    """
    size = board.size
    grid = board.grid
    results = []

    for r in range(size):
        for c in range(size):
            if grid[r][c] != EMPTY:
                continue
            # 临时放置并检查
            grid[r][c] = player
            if _quick_check_win_at(board, r, c, player):
                results.append((r, c))
            grid[r][c] = EMPTY

    return results


def _quick_check_win_at(board, r: int, c: int, player: int) -> bool:
    """检查 (r,c) 处 player 是否形成六连（假设该处已落 player 色棋子）"""
    grid = board.grid
    size = board.size

    for dr, dc in DIRECTIONS:
        count = 1
        rr, cc = r + dr, c + dc
        while 0 <= rr < size and 0 <= cc < size and grid[rr][cc] == player:
            count += 1
            rr += dr
            cc += dc
        rr, cc = r - dr, c - dc
        while 0 <= rr < size and 0 <= cc < size and grid[rr][cc] == player:
            count += 1
            rr -= dr
            cc -= dc
        if count >= 6:
            return True
    return False


def find_winning_pairs(board, player: int) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """
    找出所有"双子致胜"的空位对。
    即：在该两个空位放置 player 色棋子后，立即形成六连。
    返回 [((r1,c1),(r2,c2)), ...] 列表（去重）。

    主要覆盖模式：活四 (_XXXX_)、跳活四 (_XXX_X_, _XX_XX_, _X_XXX_)。
    算法：在所有方向上滑动 6 格窗口，查找 4 同色 + 2 空位的组合。
    """
    results: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    size = board.size
    grid = board.grid

    for dr, dc in DIRECTIONS:
        for start_r in range(size):
            for start_c in range(size):
                end_r = start_r + 5 * dr
                end_c = start_c + 5 * dc
                if not (0 <= end_r < size and 0 <= end_c < size):
                    continue

                stones = 0
                empties: list[tuple[int, int]] = []
                opponent_found = False

                for k in range(6):
                    rr = start_r + k * dr
                    cc = start_c + k * dc
                    cell = grid[rr][cc]
                    if cell == player:
                        stones += 1
                    elif cell == EMPTY:
                        empties.append((rr, cc))
                    else:
                        opponent_found = True
                        break

                if not opponent_found and stones >= 4 and len(empties) == 2:
                    # 填充这两个空位后形成六连 → 必胜对
                    pair = tuple(sorted(empties))  # 标准化排序
                    results.add(pair)

    return [list(pair) for pair in results]
