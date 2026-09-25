# sjtu-hw-to-latex

把作业 PDF（手写扫描件、拍照件、矢量墨迹件）**识别转写成 LaTeX**，
对照题目核对并订正解答，最后渲染成每题一张 PNG。

这是给 [Claude Code](https://claude.com/claude-code) 用的 skill。

## 流水线

```
PDF ──拆页──▶ 每页 PNG ──Claude 读图转写──▶ LaTeX txt ──对照题目订正──▶ 渲染 ──▶ 每题一张 PNG
```

**看图转写这一步由 Claude 亲自做**，脚本只负责两端（拆页、出图）。
所以**不需要 API key、不联网、不额外花钱**。

## 产物

```
<PDF 所在目录>/<作业名>_转换/
├── 页面/            PDF 每页渲染图（排查用，可删）
├── latex/作业.txt   只有正文，喂给渲染脚本
├── latex/作业.tex   完整可编译版，xelatex 直接出 PDF
├── 图片/第N题.png   最终交付物
└── 报告.md          订正记录 + 待核对项
```

渲染用 [MathJax](https://www.mathjax.org/) 排版、本机 Chrome/Edge 无头截图，
所以公式效果和在线作业系统的公式编辑器一致。

## 安装

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/chiyeeheh/sjtu-hw-to-latex.git ~/.claude/skills/sjtu-hw-to-latex
python -m pip install pymupdf
```

第一条是给目录兜底——`~/.claude/skills/` 不存在的话，直接 `cp` 进去会报
`cannot create directory`，所以先建出来。第二条直接把仓库克隆到技能目录里，
不用先 clone 再 cp。

还需要 **Node.js** 和 **Chrome 或 Edge**（截图用）。
Node 依赖（mathjax + puppeteer-core，约 75MB）不用手动装 ——
第一次跑 `hw_render.py` 时会自动 `npm install`。

几个坑：

- **Windows 的 cmd / PowerShell 不认 `~` 和 `mkdir -p`。** 用 Git Bash 跑，
  或者把路径换成 `%USERPROFILE%\.claude\skills\sjtu-hw-to-latex`
- 如果 `python` 不对，换成 `python3 -m pip install pymupdf`
- 装完要**重开一个 Claude Code 会话**才会加载
- 以后更新：`git -C ~/.claude/skills/sjtu-hw-to-latex pull`

## 用法

> 把 ~/Downloads/线性代数作业.pdf 转成 LaTeX，然后按题号切成图片

如果题面在另一个文件里，一并告诉它，它会把第 3 步的核对也做了：

> 这是作业 PDF，题面在同目录的 `作业1/` 文件夹里，帮我核对并改正错误

或者点名调用：`/sjtu-hw-to-latex`

## 它能做什么、不做什么

**会做**
- 把手写笔迹按最合理的数学读法转成规范 LaTeX（分数、上下标、希腊字母、矩阵、方程组）
- 处理**分页重叠**：同一段内容在上页末尾和下页开头各出现一次时只保留一次
- 丢掉页眉页脚页码日期
- 对照题面**验算**并改正错误 —— 按你原有解法的思路改，不另起炉灶换解法
- 每处改动留注释说明原文是什么、为什么改
- 列出自己**没把握**的地方（字迹看不清、符号有歧义、疑似笔误）

**不会做**
- 不会润色、不会补步骤、不会把解法改写成标准答案
- 没有题面时**跳过核对**，只做转写（报告里会写明）

## 一个格式契约

切题靠 `\noindent\textbf{题号}` 这一行标记 —— 转写和渲染之间就靠它对接。
`SKILL.md` 里列了渲染端支持的写法（`$...$`、`\[...\]`、`bmatrix`、`cases`、`xrightarrow`）
和会让 MathJax 报错的写法（标题区、`\newcommand`、`align` 环境）。

改 `hw_render.py` 时注意三个已踩过的坑：

1. HTML 里 `$...$` 和 `\(...\)` 片段必须转义 `< > &`，否则 `$s<r$` 里的 `<` 会被浏览器当标签吃掉
2. 公式容器不能加 `overflow-x:auto`，会裁掉超宽的矩阵链
3. 第一个 `\noindent\textbf{}` 之前的内容要归到第一题（跨页承接的矩阵）

## 和 sjtu-hw-split 的区别

| | sjtu-hw-split | **sjtu-hw-to-latex**（本仓库） |
|---|---|---|
| 做什么 | 裁原图 | 识别成 LaTeX，订正，再渲染 |
| 输出 | 原始扫描图的裁切 | `.tex` / `.txt` + 重新排版的图 |
| 手写原貌 | 保留 | 丢失 |
| 依赖 | pymupdf / pillow / numpy | 额外要 Node + Chrome |

**要认字就用本仓库，只要图就用 split。**
要手写原貌 → 用 `sjtu-hw-split` 那个 skill；要干净排版、或者想让它帮你查错 → 本仓库。

> 两个 skill 是配套的，可以都装。安装方式和上面一样，仓库名就是 `sjtu-hw-split`。
