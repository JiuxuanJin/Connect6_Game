"""
connect6 棋盘模块
纯数据结构，零 GUI 依赖
管理 19x19 棋盘状态
"""

from .config import BOARD_SIZE, EMPTY, BLACK, WHITE


class Board:
    """19x19 棋盘"""

    def __init__(self):
        self.size = BOARD_SIZE
        self.grid = [[EMPTY for _ in range(self.size)] for _ in range(self.size)]
        self.move_history = []  # 记录落子历史 [(row, col, player), ...]

    def is_empty(self, row: int, col: int) -> bool:
        """检查指定位置是否为空"""
        if not self.in_bounds(row, col):
            return False
        return self.grid[row][col] == EMPTY

    def in_bounds(self, row: int, col: int) -> bool:
        """检查坐标是否在棋盘内"""
        return 0 <= row < self.size and 0 <= col < self.size

    def place_stone(self, row: int, col: int, player: int) -> bool:
        """落子，成功返回 True"""
        if not self.in_bounds(row, col):
            return False
        if self.grid[row][col] != EMPTY:
            return False
        self.grid[row][col] = player
        self.move_history.append((row, col, player))
        return True

    def remove_stone(self, row: int, col: int) -> bool:
        """移除指定位置的棋子"""
        if not self.in_bounds(row, col):
            return False
        if self.grid[row][col] == EMPTY:
            return False
        self.grid[row][col] = EMPTY
        return True

    def undo_last_move(self) -> tuple[int, int, int] | None:
        """撤销最后一步落子，返回被撤销的 (row, col, player) 或 None"""
        if not self.move_history:
            return None
        row, col, player = self.move_history.pop()
        self.grid[row][col] = EMPTY
        return (row, col, player)

    def get_history(self) -> list[tuple[int, int, int]]:
        """获取落子历史"""
        return self.move_history.copy()

    def get_history_count(self) -> int:
        """获取落子总数"""
        return len(self.move_history)

    def check_win(self, row: int, col: int) -> bool:
        """检查在 (row, col) 落子后是否形成六连"""
        player = self.grid[row][col]
        if player == EMPTY:
            return False

        # 四个方向：水平、垂直、左上-右下对角线、右上-左下对角线
        directions = [
            (0, 1),    # 水平
            (1, 0),    # 垂直
            (1, 1),    # 对角线（↘）
            (1, -1),   # 对角线（↙）
        ]

        for dr, dc in directions:
            count = 1
            # 正方向
            r, c = row + dr, col + dc
            while self.in_bounds(r, c) and self.grid[r][c] == player:
                count += 1
                r += dr
                c += dc
            # 反方向
            r, c = row - dr, col - dc
            while self.in_bounds(r, c) and self.grid[r][c] == player:
                count += 1
                r -= dr
                c -= dc
            if count >= 6:
                return True
        return False

    def get_cell(self, row: int, col: int) -> int:
        """获取指定位置的棋子"""
        if self.in_bounds(row, col):
            return self.grid[row][col]
        return EMPTY

    def copy(self) -> "Board":
        """深拷贝棋盘"""
        new_board = Board()
        new_board.grid = [row[:] for row in self.grid]
        new_board.move_history = self.move_history.copy()
        return new_board

    def restore_from(self, other: "Board") -> None:
        """从另一个棋盘恢复状态"""
        self.grid = [row[:] for row in other.grid]
        self.move_history = other.move_history.copy()

    def clear(self) -> None:
        """清空棋盘"""
        for r in range(self.size):
            for c in range(self.size):
                self.grid[r][c] = EMPTY
        self.move_history.clear()