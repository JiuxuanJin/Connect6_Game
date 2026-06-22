"""
connect6 主程序入口
"""

from src.gui import GUI


def main():
    gui = GUI(use_ai=True, ai_search_depth=1, ai_enable_force_win=False, ai_ad_v=1.0)
    gui.run()


if __name__ == "__main__":
    main()