#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""考公题库 · PDF 处理工具

三个子命令：
  text  看某一页的纯文本（先用来确认 PDF 物理页与卷面页码的偏移）
  dump  批量提字 + 渲染整页为 PNG（供确认裁切区域）
  crop  按坐标裁切指定区域，输出 PNG

坐标一律用「渲染图的像素坐标」，脚本内部换算成 PDF point，避免手工折算。

依赖：pymupdf（pip install pymupdf）。没装会在启动时给出明确提示。
"""
import argparse
import os
import sys

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.stderr.write(
        "缺少依赖 pymupdf。请先安装：\n"
        "    pip install pymupdf\n"
        "（若在手机端，确认 Python 环境可用后再装）\n"
    )
    sys.exit(2)


def parse_pages(spec, total):
    """'1-40' / '29' / '1-5,9,12-14' -> [0-based 页号列表]"""
    out = []
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a), int(b)
            out.extend(range(a - 1, b))
        else:
            out.append(int(part) - 1)
    return [p for p in out if 0 <= p < total]


def parse_box(spec):
    vals = [float(x) for x in str(spec).split(",")]
    if len(vals) != 4:
        raise ValueError("--box 需要 4 个数字：x0,y0,x1,y1")
    x0, y0, x1, y1 = vals
    if x1 <= x0 or y1 <= y0:
        raise ValueError("--box 的右下角必须大于左上角")
    return x0, y0, x1, y1


def px_to_pt(px, dpi):
    return px * 72.0 / float(dpi)


def cmd_text(args):
    doc = fitz.open(args.pdf)
    try:
        pages = parse_pages(args.page, doc.page_count) if args.page else [0]
        print("PDF 共 %d 页（物理页）" % doc.page_count)
        for pno in pages:
            page = doc[pno]
            print("\n===== 物理第 %d 页 | 尺寸 %.0f x %.0f pt =====" % (
                pno + 1, page.rect.width, page.rect.height))
            txt = page.get_text()
            lines = txt.splitlines()
            if args.head:
                lines = lines[:args.head]
                txt = "\n".join(lines)
                print("[仅显示前 %d 行]" % args.head)
            print(txt)
    finally:
        doc.close()


def cmd_dump(args):
    doc = fitz.open(args.pdf)
    try:
        pages = parse_pages(args.pages, doc.page_count) if args.pages else list(range(doc.page_count))
        outdir = args.out or "./pdf_work"
        os.makedirs(outdir, exist_ok=True)
        print("PDF 共 %d 页，本次处理 %d 页，输出目录 %s" % (
            doc.page_count, len(pages), os.path.abspath(outdir)))
        zoom = float(args.dpi) / 72.0
        mat = fitz.Matrix(zoom, zoom)
        for pno in pages:
            page = doc[pno]
            print("\n===== 物理第 %d 页（%.0f x %.0f pt）=====" % (
                pno + 1, page.rect.width, page.rect.height))
            print(page.get_text())
            png = os.path.join(outdir, "page-%03d.png" % (pno + 1))
            pix = page.get_pixmap(matrix=mat, alpha=False)
            pix.save(png)
            print("[已渲染] %s  %d x %d px  (%d DPI)" % (
                os.path.relpath(png, outdir), pix.width, pix.height, args.dpi))
    finally:
        doc.close()


def cmd_crop(args):
    doc = fitz.open(args.pdf)
    try:
        pages = parse_pages(args.page, doc.page_count)
        if not pages:
            print("页号超出范围")
            return
        pno = pages[0]
        page = doc[pno]
        x0, y0, x1, y1 = parse_box(args.box)
        dpi = float(args.dpi)
        # 像素 -> PDF point
        rect = fitz.Rect(px_to_pt(x0, dpi), px_to_pt(y0, dpi),
                         px_to_pt(x1, dpi), px_to_pt(y1, dpi))
        pw, ph = page.rect.width, page.rect.height
        if rect.x1 > pw + 1 or rect.y1 > ph + 1 or rect.x0 < -1 or rect.y0 < -1:
            print("警告：裁切框超出页面范围（页面 %.0f x %.0f pt）。已自动收拢到页面内。" % (pw, ph))
            rect = fitz.Rect(max(0, rect.x0), max(0, rect.y0),
                             min(pw, rect.x1), min(ph, rect.y1))
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
        out = args.out
        if not out:
            base = os.path.splitext(os.path.basename(args.pdf))[0]
            out = "%s-p%d-%d_%d_%d_%d.png" % (base, pno + 1, x0, y0, x1, y1)
        pix.save(out)
        print("已输出 %s  %d x %d px" % (os.path.abspath(out), pix.width, pix.height))
        print("提示：请肉眼看一遍图片底部，确认没有把下一题的题干带进来。")
    finally:
        doc.close()


def main():
    ap = argparse.ArgumentParser(description="考公题库 PDF 处理工具")
    sub = ap.add_subparsers(dest="cmd")

    p1 = sub.add_parser("text", help="看某页纯文本")
    p1.add_argument("pdf")
    p1.add_argument("--page", default="", help="页号，支持 1-5 或 29")
    p1.add_argument("--head", type=int, default=0, help="只显示前 N 行")
    p1.set_defaults(func=cmd_text)

    p2 = sub.add_parser("dump", help="批量提字 + 渲染整页 PNG")
    p2.add_argument("pdf")
    p2.add_argument("--pages", default="", help="如 1-40；省略则全书")
    p2.add_argument("--dpi", type=int, default=150)
    p2.add_argument("--out", default="./pdf_work")
    p2.set_defaults(func=cmd_dump)

    p3 = sub.add_parser("crop", help="按坐标裁切")
    p3.add_argument("pdf")
    p3.add_argument("--page", required=True, help="页号（物理页，从 1 开始）")
    p3.add_argument("--box", required=True, help="像素坐标 x0,y0,x1,y1（按 --dpi 渲染后的像素）")
    p3.add_argument("--dpi", type=int, default=150)
    p3.add_argument("--out", default="")
    p3.set_defaults(func=cmd_crop)

    args = ap.parse_args()
    if not getattr(args, "func", None):
        ap.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
