#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""LaTeX 正文 -> 每题一个 HTML ->（调本机 Chrome）每题一张 PNG。

    python hw_render.py <latex.txt> <outdir> [--width 1120] [--scale 2] [--prefix 第]

输入文件里用 \\noindent\\textbf{题号} 标记每道大题的开头。

输出（stdout，每行一条）：
    WARN <提示>
    PROB <序号> <题号> <图片绝对路径>
    DONE <题数>
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML_DIR = HERE / "html"
CIRCLED = {str(i + 1): chr(0x2460 + i) for i in range(20)}

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]

TEMPLATE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<script>
MathJax = {
  tex: {inlineMath: [['\\\\(', '\\\\)']], displayMath: [['$$', '$$']]},
  svg: {fontCache: 'local'},
  startup: {typeset: true}
};
</script>
<script src="../node_modules/mathjax/es5/tex-svg.js"></script>
<style>
  body { margin:0; padding:36px 44px; background:#fff;
         font-family:"Times New Roman","SimSun",serif; font-size:19px;
         color:#111; width:__WIDTH__px; box-sizing:border-box; }
  h2 { font-size:22px; margin:0 0 14px;
       font-family:"Times New Roman","SimSun",serif; }
  h2 .rest { font-weight:normal; font-size:20px; }
  p { margin:9px 0; line-height:1.85; }
  .math { margin:12px 0; }
  mjx-container[display="true"] { text-align:left !important;
                                  margin-left:1.4em;
                                  overflow-x:visible !important; }
  ol, ul { margin:10px 0 10px 1.6em; padding:0; }
  li { margin:11px 0; line-height:1.8; }
  ol.circled, ol.numbered { list-style:none; margin-left:0; padding-left:0; }
  ol.circled > li, ol.numbered > li { position:relative; padding-left:2.6em; }
  .lbl { position:absolute; left:0;
         font-family:"Times New Roman","Segoe UI Symbol",sans-serif; }
  ul.plain { list-style:none; margin-left:1.2em; }
  ul.plain > li:before { content:"\\2022\\00a0\\00a0"; }
  ul.plain > li > p { display:inline; }
</style></head>
<body>
__BODY__
</body></html>
"""

WARNINGS = []

# 这些环境只是排版容器，对 HTML 没意义，直接拆掉，内容照常渲染
LAYOUT_ENVS = ("center", "flushleft", "flushright", "quote", "quotation",
               "abstract", "titlepage", "sloppypar", "samepage")


def preprocess(latex):
    """去掉对逐题 HTML 没意义、又会让 MathJax 报错的排版外壳。"""
    if "\\begin{document}" in latex:
        latex = latex.split("\\begin{document}", 1)[1]
    if "\\end{document}" in latex:
        latex = latex.split("\\end{document}", 1)[0]

    for env in LAYOUT_ENVS:
        latex = latex.replace("\\begin{%s}" % env, "")
        latex = latex.replace("\\end{%s}" % env, "")

    # {\Large\bfseries 标题} -> 标题 ；{a_{11}} 这类不受影响（组内没有反斜杠命令）
    latex = re.sub(r"\{\s*(?:\\[a-zA-Z]+\s*)+([^{}\\]*)\}", r"\1", latex)

    # 整行注释
    return "\n".join(l for l in latex.split("\n") if not l.strip().startswith("%"))


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _cjk_in_math(tex):
    for ch in tex:
        if "一" <= ch <= "鿿":
            return True
    return False


def _note_cjk(tex):
    if _cjk_in_math(tex):
        snippet = re.sub(r"\s+", " ", tex.strip())[:48]
        WARNINGS.append("公式里混了中文（会用系统字体画，和正文略有差异）：%s" % snippet)


def inline(s):
    """行内文本：$...$ 和 \\(...\\) 交 MathJax，其余转义。

    数学片段也要转义——浏览器会把 &lt; 还原成 <，MathJax 读到的是还原后的文本；
    不转义的话 $s<r$ 里的 < 会被 HTML 解析器当成标签吃掉。
    """
    s = re.sub(r"\$\\cn\{(\d)\}\$", lambda m: CIRCLED.get(m.group(1), m.group(1)), s)
    s = s.replace("\\ ", " ")
    s = re.sub(r"\\noindent\b", "", s)      # 题号标记用掉了，块内再出现就是残留

    stash = []

    def _keep(mm):
        stash.append(mm.group(1))
        return "\x00%d\x00" % (len(stash) - 1)

    s = re.sub(r"\\\((.*?)\\\)", _keep, s, flags=re.S)

    parts = s.split("$")
    out = []
    for i, p in enumerate(parts):
        if i % 2:
            _note_cjk(p)
            out.append("\\(" + esc(p) + "\\)")
        else:
            out.append(esc(p))
    s = "".join(out)

    def _restore(mm):
        tex = stash[int(mm.group(1))]
        _note_cjk(tex)
        return "\\(" + esc(tex) + "\\)"

    s = re.sub(r"\x00(\d+)\x00", _restore, s)
    # 转义之后再换 \textbf，否则 <b> 会被当成文本转义掉
    return re.sub(r"\\textbf\{([^{}]*)\}", r"<b>\1</b>", s)


def disp(tex):
    _note_cjk(tex)
    return '<div class="math">$$' + esc(tex.strip()) + "$$</div>"


def _flush(buf, out):
    if buf:
        out.append("<p>" + inline(" ".join(buf)) + "</p>")
        buf.clear()


def render_block(lines):
    out, buf, i, n = [], [], 0, len(lines)
    while i < n:
        s = lines[i].strip()

        if s in ("", "\\medskip", "\\bigskip", "\\smallskip"):
            _flush(buf, out)
            i += 1
            continue

        if s.startswith("\\["):
            _flush(buf, out)
            tex, rest = [], s[2:]
            if "\\]" in rest:
                tex.append(rest.split("\\]")[0])
                i += 1
            else:
                tex.append(rest)
                i += 1
                while i < n and "\\]" not in lines[i]:
                    tex.append(lines[i])
                    i += 1
                tex.append(lines[i].split("\\]")[0] if i < n else "")
                i += 1
            out.append(disp("\n".join(tex)))
            continue

        if s.startswith("$$"):
            _flush(buf, out)
            tex, rest = [], s[2:]
            if "$$" in rest:
                tex.append(rest.split("$$")[0])
                i += 1
            else:
                tex.append(rest)
                i += 1
                while i < n and "$$" not in lines[i]:
                    tex.append(lines[i])
                    i += 1
                tex.append(lines[i].split("$$")[0] if i < n else "")
                i += 1
            out.append(disp("\n".join(tex)))
            continue

        m = re.match(r"\\begin\{(align\*?|gather\*?|equation\*?|eqnarray\*?|multline\*?)\}", s)
        if m:
            _flush(buf, out)
            env = m.group(1)
            tex = [s]
            i += 1
            while i < n and ("\\end{%s}" % env) not in lines[i]:
                tex.append(lines[i])
                i += 1
            if i < n:
                tex.append(lines[i])
                i += 1
            out.append(disp("\n".join(tex)))
            continue

        m = re.match(r"\\begin\{(enumerate|itemize)\}(\[[^\]]*\])?", s)
        if m:
            _flush(buf, out)
            kind = m.group(1)
            circled = kind == "enumerate" and ("\\cn" in s)
            i += 1
            items, cur = [], []
            while i < n and not lines[i].strip().startswith("\\end{" + kind + "}"):
                t = lines[i]
                if t.strip().startswith("\\item"):
                    items.append(cur)
                    cur = []
                    t = t.strip()[5:]
                    if t.strip():
                        cur.append(t)
                elif t.strip():
                    cur.append(t)
                i += 1
            items.append(cur)
            i += 1
            items = [x for x in items if any(y.strip() for y in x)]

            tag = "ol" if kind == "enumerate" else "ul"
            cls = "circled" if circled else ("plain" if kind == "itemize" else "numbered")
            html = ['<%s class="%s">' % (tag, cls)]
            for idx, it in enumerate(items, 1):
                inner = render_block(it)
                if kind == "enumerate":
                    lab = CIRCLED.get(str(idx), str(idx)) if circled else "(%d)" % idx
                    inner = '<span class="lbl">%s</span>%s' % (lab, inner)
                html.append("<li>%s</li>" % inner)
            html.append("</%s>" % tag)
            out.append("\n".join(html))
            continue

        buf.append(s)
        i += 1
    _flush(buf, out)
    return "\n".join(out)


def split_problems(latex):
    """按 \\noindent\\textbf{N.} 切成 [(题号, 行内说明, 正文行列表), ...]。

    第一个开题标记之前的内容会归到第一题里（典型情况：承接上一页末尾的
    矩阵，因为跨页被单独切了出来），不能丢。
    """
    pattern = re.compile(r"\\noindent\s*\\textbf\{([^}]*)\}")
    marks = list(pattern.finditer(latex))
    if not marks:
        return []
    preamble = latex[:marks[0].start()].strip()
    problems = []
    for k, m in enumerate(marks):
        end = marks[k + 1].start() if k + 1 < len(marks) else len(latex)
        chunk = latex[m.end():end]
        first_line, _, remainder = chunk.partition("\n")
        lines = remainder.split("\n")
        if k == 0 and preamble:
            lines = preamble.split("\n") + [""] + lines
        problems.append((m.group(1).strip(), first_line.strip(), lines))
    return problems


def find_chrome():
    for p in CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    raise SystemExit("没找到 Chrome 或 Edge，请装一个，或改 hw_render.py 里的 CHROME_CANDIDATES。")


def ensure_node_deps():
    if (HERE / "node_modules" / "mathjax" / "es5" / "tex-svg.js").exists():
        return
    print("WARN 首次运行，正在装 Node 依赖（约 75MB，等一两分钟）…")
    r = subprocess.run(["npm", "install"], cwd=str(HERE),
                       capture_output=True, text=True, shell=(os.name == "nt"))
    if r.returncode != 0:
        raise SystemExit("npm install 失败：\n%s\n%s" % (r.stdout, r.stderr))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("latex")
    ap.add_argument("outdir")
    ap.add_argument("--width", type=int, default=1120)
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--label", default="第")   # 输出文件名：第N题.png
    a = ap.parse_args()

    # 容忍两种输入：只有正文的 txt，或者完整可编译的 .tex
    latex = preprocess(Path(a.latex).read_text(encoding="utf-8"))
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    ensure_node_deps()

    for old in HTML_DIR.glob("*.html"):
        old.unlink()
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    del WARNINGS[:]

    problems = split_problems(latex)
    if not problems:
        raise SystemExit("没找到开题标记 \\noindent\\textbf{...}，请检查 LaTeX 正文。")

    for idx, (head, rest, lines) in enumerate(problems, 1):
        title = inline(head)
        if rest:
            title += ' <span class="rest">%s</span>' % inline(rest)
        body = "<h2>%s</h2>\n%s" % (title, render_block(lines))
        (HTML_DIR / ("p%02d.html" % idx)).write_text(
            TEMPLATE.replace("__WIDTH__", str(a.width)).replace("__BODY__", body),
            encoding="utf-8")

    for w in WARNINGS:
        print("WARN " + w)

    cfg = {"chrome": find_chrome(), "htmlDir": str(HTML_DIR), "outDir": str(out.resolve()),
           "width": a.width, "scale": a.scale}
    cfg_path = HERE / "_jobs.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")

    r = subprocess.run(["node", "shoot.js", str(cfg_path)], cwd=str(HERE),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       shell=(os.name == "nt"))
    if r.returncode != 0:
        raise SystemExit("截图失败：\n%s\n%s" % (r.stdout, r.stderr))

    shot = {}
    for line in r.stdout.splitlines():
        if line.startswith("OK "):
            shot[Path(line[3:].strip()).stem] = Path(line[3:].strip())
        elif line.startswith("WARN "):
            print("WARN " + line[5:])

    made = 0
    for idx, (head, _, _) in enumerate(problems, 1):
        src = shot.get("p%02d" % idx)
        if not src:
            continue
        lab = re.sub(r"[^\w\u4e00-\u9fff]", "", head) or str(idx)
        dst = out / ("%s%s题.png" % (a.label, lab))
        if dst.exists():
            dst.unlink()
        src.replace(dst)
        made += 1
        print("PROB %d %s %s" % (idx, head, dst.resolve()))
    print("DONE %d" % made)


if __name__ == "__main__":
    main()
