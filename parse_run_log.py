# -*- coding: utf-8 -*-
"""
Đọc log một lần chạy LogCL / DEPTH và xuất báo cáo gọn.

Cách dùng:
    python parse_run_log.py <đường_dẫn_log> [--name "LogCL"] [--out report.md]

Nếu lúc chạy bạn lưu output ra file, ví dụ:
    python src/main.py ... *> logcl_run.txt        # PowerShell
    python src/main.py ... 2>&1 | tee logcl_run.txt # bash
rồi:  python parse_run_log.py logcl_run.txt --name LogCL

Lưu ý: nhãn in trong code là "(1,3,5)" NHƯNG hits thực tế = [1,3,10]
(rgcn/utils.py), nên 4 cột là: MRR, Hits@1, Hits@3, Hits@10.
"""
import re, sys, argparse


def read_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8", "utf-16", "utf-16-le", "latin-1"):
        try:
            t = raw.decode(enc)
            if t.count("\x00") == 0:
                return t
        except Exception:
            pass
    return raw.decode("utf-8", errors="ignore")


def parse(text):
    info = {}
    # config
    m = re.search(r"Namespace\((.*)\)", text)
    if m:
        cfg = m.group(1)
        for k in ["dataset", "use_cl", "train_history_len", "lr", "n_hidden",
                  "encoder", "decoder", "temperature", "pre_weight", "n_layers"]:
            mm = re.search(rf"{k}=([^,]+)", cfg)
            if mm:
                info[k] = mm.group(1).strip().strip("'")
    info["unified_path"] = bool(re.search(r"\[unified\] inline path head", text))
    info["fusion_loaded"] = bool(re.search(r"\[fusion\] loaded", text))

    # epochs (loss)
    epochs = re.findall(r"Epoch (\d+) \| Ave Loss:\s*([\d.]+|nan)", text)

    # gamma trend
    gammas = re.findall(r"\[fusion\] path_gamma\s*=\s*([\d.\-]+)", text)

    # best epoch
    mb = re.search(r"Using best epoch\s*:\s*(\d+)", text)
    info["best_epoch"] = int(mb.group(1)) if mb else None

    # all_filter rows (in order). 4 số = MRR, H@1, H@3, H@10
    rows = re.findall(
        r"\(all_filter\)[^:]*:\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)", text)
    rows = [tuple(float(x) for x in r) for r in rows]

    # tách validation vs test: test là all_filter SAU mốc "start testing"
    ti = text.find("start testing")
    n_val = None
    if ti != -1:
        # đếm số all_filter trước mốc test
        n_val = len(re.findall(
            r"\(all_filter\)[^:]*:\s*[\d.]+,\s*[\d.]+,\s*[\d.]+,\s*[\d.]+",
            text[:ti]))
    if n_val is None:
        val_rows, test_row = rows, None
    else:
        val_rows = rows[:n_val]
        test_row = rows[n_val] if len(rows) > n_val else None

    return info, epochs, gammas, val_rows, test_row


def fmt(v):
    return "%.4f" % v


def build_report(name, info, epochs, gammas, val_rows, test_row):
    L = []
    L.append("# BÁO CÁO CHẠY — %s (ICEWS14)" % name)
    L.append("")
    L.append("## Cấu hình")
    keys = [("dataset", "dataset"), ("use_cl", "use_cl"),
            ("train_history_len", "history_len"), ("lr", "lr"),
            ("n_hidden", "hidden"), ("encoder", "encoder"),
            ("decoder", "decoder"), ("temperature", "temperature")]
    L.append("| Tham số | Giá trị |")
    L.append("|---|---|")
    for k, label in keys:
        if k in info:
            L.append("| %s | %s |" % (label, info[k]))
    L.append("| inline path head | %s |" % ("CÓ (DEPTH)" if info.get("unified_path") else "không"))
    if info.get("fusion_loaded"):
        L.append("| fusion (pkl) | CÓ |")
    if info.get("best_epoch") is not None:
        L.append("| best epoch | %d |" % info["best_epoch"])
    L.append("")

    # validation theo epoch
    L.append("## Validation (all_filter) theo epoch")
    L.append("| Epoch | MRR | Hits@1 | Hits@3 | Hits@10 |")
    L.append("|---|---|---|---|---|")
    for i, r in enumerate(val_rows, 1):
        star = "  ← best" if info.get("best_epoch") == i else ""
        L.append("| %d | %s | %s | %s | %s |%s" %
                 (i, fmt(r[0]), fmt(r[1]), fmt(r[2]), fmt(r[3]),
                  ("  **%s**" % star.strip()) if star else ""))
    if val_rows:
        best = max(val_rows, key=lambda r: r[0])
        L.append("")
        L.append("- Valid MRR cao nhất: **%s**" % fmt(best[0]))
    L.append("")

    # gamma
    if gammas:
        gv = [float(g) for g in gammas]
        L.append("## path_gamma (γ)")
        L.append("- γ đầu: %.4f  ·  γ cuối: %.4f  ·  %s" %
                 (gv[0], gv[-1], "DƯƠNG → mô hình dùng nhánh path"
                  if gv[-1] > 1e-4 else "≈0"))
        L.append("")

    # test
    L.append("## KẾT QUẢ TEST (all_filter)")
    if test_row:
        L.append("| MRR | Hits@1 | Hits@3 | Hits@10 |")
        L.append("|---|---|---|---|")
        L.append("| **%s** | **%s** | **%s** | **%s** |" %
                 (fmt(test_row[0]), fmt(test_row[1]), fmt(test_row[2]), fmt(test_row[3])))
        L.append("")
        L.append("So với 2 paper (×100):")
        L.append("| Mô hình | MRR | Hits@1 | Hits@3 | Hits@10 |")
        L.append("|---|---|---|---|---|")
        L.append("| CognTKE (paper) | 46.06 | 36.49 | 51.11 | 64.49 |")
        L.append("| LogCL (paper) | 48.87 | 37.76 | 54.71 | 70.26 |")
        L.append("| %s | %.2f | %.2f | %.2f | %.2f |" %
                 (name, test_row[0]*100, test_row[1]*100, test_row[2]*100, test_row[3]*100))
    else:
        L.append("(Không tìm thấy dòng test — log có thể chưa chạy xong phần testing.)")
    L.append("")
    L.append("*Ghi chú: cột thứ 4 là Hits@10 (nhãn code in nhầm \"(1,3,5)\"; hits thật = [1,3,10]).*")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log", help="đường dẫn file log")
    ap.add_argument("--name", default="Run", help="tên mô hình (vd LogCL / DEPTH)")
    ap.add_argument("--out", default=None, help="ghi báo cáo .md (mặc định: in ra màn hình)")
    a = ap.parse_args()

    text = read_text(a.log)
    info, epochs, gammas, val_rows, test_row = parse(text)
    rep = build_report(a.name, info, epochs, gammas, val_rows, test_row)

    if a.out:
        open(a.out, "w", encoding="utf-8").write(rep)
        print("[ok] wrote report ->", a.out)
    else:
        # in ra (an toàn cho console Windows)
        sys.stdout.buffer.write(rep.encode("utf-8", errors="replace"))
        sys.stdout.buffer.write(b"\n")


if __name__ == "__main__":
    main()
