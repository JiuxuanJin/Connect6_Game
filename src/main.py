"""
connect6 主程序入口
启动六子棋游戏
"""
import sys
import os
import pygame

# 确保项目根目录在 sys.path 中，支持直接运行此文件
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.gui import GUI


def main():
    app = GUI(use_ai=True, ai_search_depth=1, ai_enable_force_win=False, ai_ad_v=1.0)  # 默认人机对战，深度1，不检测必胜手，攻防均衡
    app.run()


if __name__ == "__main__":
    main()
