#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PDF -> 每页一张 PNG，供 Claude 读图转写。

    python hw_pdf.py <pdf> <outdir> [--long-edge 1568] [--keep-blank]

输出（stdout，每行一条，方便调用方解析）：
    PAGE <页码> <像素宽>x<像素高> <文件绝对路径>
    SKIP <页码> 空白页
    DONE <页数> 页
"""
import argparse
import sys
from pathlib import Path

import pymupdf


def is_blank(pix, step=7, threshold=250):
    """抽样判断是否几乎全白。"""
    s, n = pix.samples, pix.n
    total = hits = 0
    for y in range(0, pix.height, step):
        row = y * pix.stride
        for x in range(0, pix.width, step):
            off = row + x * n
            total += 1
            if s[off] >= threshold and s[off + 1] >= threshold and s[off + 2] >= threshold:
                hits += 1
    return total > 0 and hits / total > 0.995


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("outdir")
    ap.add_argument("--long-edge", type=int, default=1568)
    ap.add_argument("--keep-blank", action="store_true")
    a = ap.parse_args()

    pdf = Path(a.pdf)
    if not pdf.exists():
        sys.exit("找不到 PDF：%s" % pdf)
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(str(pdf))
    kept = 0
    for i, page in enumerate(doc, 1):
        w, h = page.rect.width, page.rect.height
        if w <= 0 or h <= 0:
            continue
        z = a.long_edge / max(w, h)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z))
        if not a.keep_blank and is_blank(pix):
            print("SKIP %d 空白页" % i)
            continue
        fn = out / ("page%02d.png" % i)
        pix.save(str(fn))
        kept += 1
        print("PAGE %d %dx%d %s" % (i, pix.width, pix.height, fn.resolve()))
    doc.close()
    print("DONE %d 页" % kept)


if __name__ == "__main__":
    main()
