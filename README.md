# 六子棋 Connect6

人机对局六子棋游戏，基于 Pygame 实现图形化界面，支持人机对战，AI 采用 Minimax + Alpha-Beta 剪枝算法，包含必胜手检测策略和多重威胁检测策略。

## 项目功能

- **完整对局规则**：19×19 棋盘，黑先白后，黑方第一手落 1 子，之后双方轮流落 2 子，横/竖/对角线连成 6 子获胜
- **图形化界面**：主菜单、规则介绍、模式选择、对局界面、获胜界面
- **人机对战**：可选执黑或执白，多个可调参数自由搭配
- **悔棋功能**：每轮最多使用 1 次悔棋，开局前 2 次落子不能悔棋
- **落子确认机制**：未确认前可撤销落子，确认后不可修改
- **高亮显示**：新落黑子蓝色轮廓，新落白子红色轮廓，确认后持续高亮至下一回合
- **AI 落子动画**：AI 落子逐步展示，观感流畅

## 核心算法介绍

AI 引擎采用 **Minimax 搜索 + Alpha-Beta 剪枝 + 启发式评分函数**，搜索深度可配置（1-3层）。

**局面评估** 采用四种独立模式，分别评分：

| 模式 | 说明 | 示例 |
|------|------|------|
| 活 (Live) | 两端开放，连续无空 | `_XXX_` 活三 |
| 冲 (Rush) | 一端开放，一端被堵，连续无空 | `#XXX_` 冲三 |
| 跳活 (Jump Live) | 两端开放，中间有一个空位 | `_XX_X_` 跳活三 |
| 跳冲 (Jump Rush) | 一端开放，中间有一个空位 | `#XX_X_` 跳冲三 |

每种模式按连子数量赋予不同分值，连子越长分越高，形成 6 连为极高分值（触发胜利）。

**候选着法优化**：
仅考虑距离已有棋子 3 格以内的空位，大幅减少搜索空间，优化搜索速度。

**必胜手检测**：
每次执行 minimax 搜索前，先搜索是否存在一步必胜的走法。
1. AI 自己有必杀手 → 直接落必胜子，跳过后续搜索；
2. 对手有必杀手 → 逐颗尝试堵，威胁消除即停止堵子；
3. 剩余子由 minimax 搜索决定。

**双重威胁检测**：
如果一个落子会产生 2 个及以上高威胁棋型（活三及更高评分的棋型），相应评价分会有 3 倍额外权重，AI会优先考虑。

**攻防倾向**：
位置评分来自攻防评分的加权和，攻防倾向值越大，进攻评分权重越高，反之防守评分权重越高。

**位置权重**：
评分附加棋盘位置权重，中心最高，权重为 1 ，四周较低，最低权重降低至 0.7 。


## 仓库结构

```
Connect6/
├── main.py              # 主程序入口（根目录启动脚本）
├── src/                 # 源代码包
│   ├── __init__.py      # 包初始化文件
│   ├── main.py          # 备用入口（由根 main.py 调用 GUI）
│   ├── config.py        # 常量与配置（棋盘大小、颜色、字体等）
│   ├── board.py         # 棋盘逻辑（纯数据结构，零 GUI 依赖）
│   ├── game_controller.py  # 对局控制器（回合管理、胜负判断、悔棋、AI线程）
│   ├── ai.py            # AI 引擎（Minimax + Alpha-Beta 剪枝）
│   ├── evaluate.py      # 局面评估（活/冲/跳活/跳冲 四种模式评分）
│   └── gui.py           # 图形界面（Pygame 实现，含主菜单、规则介绍、对局界面）
├── font/                # 字体文件
│   └── simhei.ttf       # 黑体（项目自带中文字体，防止 pygame 报错）
├── requirements.txt     # Python 依赖清单
├── Connect6_Game.spec   # PyInstaller 打包配置文件（用于生成 exe）
├── Connect6_Game.exe    # 独立可执行文件（已打包，可直接运行）
├── README.md            # 项目说明
├── LICENSE              # 开源协议
└── .gitignore           # Git 忽略规则
```

## 运行指南

### 方式一：Python 源码运行

1. **安装 Python 3.10+**
2. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```
3. **运行游戏**：
   ```bash
   cd Connect6
   python main.py
   ```

### 方式二：独立可执行文件（仅限 Windows）

运行 `Connect6_Game.exe`（已打包所有依赖，在 Windows 中无需任何环境即可直接运行）。

**该 .exe 由 Windows 平台 PyInstaller 生成，只能在 Windows 系统上运行**。macOS 或 Linux 用户请使用方式一运行源码，或在对应系统上自行打包。

### 方式三：自行打包

```bash
pip install pyinstaller
cd Connect6
pyinstaller --name Connect6_Game --add-data "font/simhei.ttf:font" --add-data "src:src" --hidden-import src.ai --hidden-import src.evaluate --noconsole --onefile main.py
```
生成的 exe 位于 `dist/` 目录下。


## AI声明

本项目所有代码由 AI 辅助编程工具（deepseek v4 pro 接入 VScode Cline）辅助生成。AI 引擎核心代码与评价函数核心代码已经过人工审阅和调试，作者可以确保其正确性；其他部分代码经过多轮运行测试和试玩，均能稳定实现预期功能。

项目架构、AI 对弈逻辑、不同模式的评价函数，均由作者本人人工设计。
