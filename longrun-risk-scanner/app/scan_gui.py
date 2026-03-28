"""
GUI: chọn đường dẫn, chạy scan, hiển thị kết quả ngay trong cửa sổ (không cần tự mở .json).
Run: python app/scan_gui.py or CHAY_SCAN.bat / CHAY_SCAN.sh
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent


def _run_scan(path: str) -> tuple[int, str, str]:
    main_py = ROOT / "app" / "main.py"
    proc = subprocess.run(
        [sys.executable, str(main_py), "scan", "--path", path],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _extract_json_path(stdout: str) -> Optional[str]:
    for line in stdout.splitlines():
        line = line.strip()
        if line.upper().startswith("JSON:"):
            return line.split(":", 1)[1].strip()
    m = re.search(r"^JSON:\s*(.+)$", stdout, re.MULTILINE | re.IGNORECASE)
    return m.group(1).strip() if m else None


def _format_report(data: dict) -> str:
    """Build readable text from export JSON payload."""
    lines: list[str] = []
    scan = data.get("scan") or {}
    summary = data.get("summary") or {}
    findings = data.get("findings") or []

    lines.append("=== KẾT QUẢ SCAN ===\n")
    lines.append(f"Phiên (scan) ID: {scan.get('id', '?')}")
    lines.append(f"Thư mục / gốc quét: {scan.get('root_path', '')}")
    lines.append(f"Tổng finding: {summary.get('total_findings', len(findings))}")
    by_s = summary.get("by_status") or {}
    by_v = summary.get("by_severity") or {}
    if by_s:
        lines.append(f"Theo trạng thái: {by_s}")
    if by_v:
        lines.append(f"Theo mức nghiêm trọng: {by_v}")
    lines.append("")

    if not findings:
        lines.append("(Không có ứng viên rủi ro nào được ghi nhận.)")
        return "\n".join(lines)

    lines.append("--- Danh sách finding ---\n")
    for f in findings:
        fid = f.get("id", "?")
        rid = f.get("risk_id", "")
        rname = f.get("risk_name", "")
        fp = f.get("file_path", "")
        ls = f.get("line_start")
        le = f.get("line_end")
        loc = f"{fp}:{ls}-{le}" if ls is not None and le is not None else fp
        lines.append(f"[{fid}] {rid} — {rname}")
        lines.append(f"    Vị trí: {loc}")
        lines.append(f"    Trạng thái: {f.get('status')} | tin cậy: {f.get('confidence')} | mức: {f.get('severity')}")
        reason = (f.get("initial_reason") or "").strip()
        if reason:
            lines.append(f"    Lý do: {reason}")
        near = (f.get("near_fix") or "").strip()
        if near:
            lines.append(f"    Gợi ý gần: {near[:300]}{'…' if len(near) > 300 else ''}")
        lines.append("")
    return "\n".join(lines)


def _run_cli(args: list[str]) -> tuple[int, str, str]:
    """Run app/main.py with extra args; cwd = project root."""
    main_py = ROOT / "app" / "main.py"
    proc = subprocess.run(
        [sys.executable, str(main_py)] + args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _open_folder(path: Path) -> None:
    path = path.resolve()
    if sys.platform == "win32":
        os_cmd = ["explorer", "/select,", str(path)] if path.is_file() else ["explorer", str(path)]
        try:
            subprocess.Popen(os_cmd, shell=False)
        except OSError:
            subprocess.Popen(["explorer", str(path.parent if path.is_file() else path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path if path.is_dir() else path.parent)])
    else:
        subprocess.Popen(["xdg-open", str(path if path.is_dir() else path.parent)])


def main() -> None:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, scrolledtext, ttk
    except ImportError as e:
        print("Tkinter not available:", e, file=sys.stderr)
        print("Install Python with Tcl/Tk, or use: python app/main.py scan --path <path>", file=sys.stderr)
        sys.exit(1)

    win = tk.Tk()
    win.title("longrun-risk-scanner — scan Java")
    win.minsize(720, 520)

    frm = ttk.Frame(win, padding=10)
    frm.pack(fill=tk.BOTH, expand=True)

    ttk.Label(
        frm,
        text="Dán đường dẫn thư mục hoặc file .java:",
    ).pack(anchor=tk.W)

    path_var = tk.StringVar()
    ent = ttk.Entry(frm, textvariable=path_var, width=80)
    ent.pack(fill=tk.X, pady=(6, 4))

    btns = ttk.Frame(frm)
    btns.pack(fill=tk.X)

    def browse_dir() -> None:
        p = filedialog.askdirectory(title="Chọn thư mục cần scan")
        if p:
            path_var.set(p)

    def browse_file() -> None:
        p = filedialog.askopenfilename(
            title="Chọn file .java",
            filetypes=[("Java", "*.java"), ("All", "*.*")],
        )
        if p:
            path_var.set(p)

    ttk.Button(btns, text="Chọn thư mục…", command=browse_dir).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(btns, text="Chọn file .java…", command=browse_file).pack(side=tk.LEFT, padx=(0, 8))

    ttk.Label(
        frm,
        text="Ô trên: log lệnh. Ô dưới: kết quả scan (đọc từ báo cáo JSON — hiện ngay sau khi xong).",
        font=("Segoe UI", 9),
        foreground="#444",
    ).pack(anchor=tk.W, pady=(8, 4))

    pan = ttk.PanedWindow(frm, orient=tk.VERTICAL)
    pan.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    out = scrolledtext.ScrolledText(pan, height=8, wrap=tk.WORD, font=("Consolas", 9))
    pan.add(out, weight=0)

    result_box = scrolledtext.ScrolledText(pan, height=18, wrap=tk.WORD, font=("Consolas", 10))
    pan.add(result_box, weight=1)

    last_json_path: list[Optional[str]] = [None]
    last_scan_id: list[Optional[int]] = [None]

    result_btns = ttk.Frame(frm)
    result_btns.pack(fill=tk.X, pady=(4, 0))

    verify_row = ttk.Frame(frm)
    verify_row.pack(fill=tk.X, pady=(6, 0))

    finding_id_var = tk.StringVar(value="")

    def open_last_json() -> None:
        jp = last_json_path[0]
        if jp and Path(jp).is_file():
            if sys.platform == "win32":
                os.startfile(jp)
            else:
                import webbrowser

                webbrowser.open(Path(jp).as_uri())

    def open_scans_dir() -> None:
        d = ROOT / "scans"
        if d.is_dir():
            _open_folder(d)

    ttk.Button(result_btns, text="Mở file JSON vừa tạo", command=open_last_json).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(result_btns, text="Mở thư mục scans", command=open_scans_dir).pack(side=tk.LEFT)

    btn_verify_all = ttk.Button(
        verify_row,
        text="Verify toàn bộ phiên (local + LLM nếu bật .env)",
        state="disabled",
    )
    btn_verify_all.pack(side=tk.LEFT, padx=(0, 8))

    ttk.Label(verify_row, text="Verify 1 finding — ID:").pack(side=tk.LEFT, padx=(12, 4))
    ent_fid = ttk.Entry(verify_row, textvariable=finding_id_var, width=10)
    ent_fid.pack(side=tk.LEFT, padx=(0, 6))

    btn_verify_one = ttk.Button(verify_row, text="Verify finding này", state="disabled")
    btn_verify_one.pack(side=tk.LEFT)

    def _set_verify_enabled(ok: bool) -> None:
        st = "normal" if ok else "disabled"
        btn_verify_all.configure(state=st)
        btn_verify_one.configure(state=st)

    def verify_all_session() -> None:
        sid = last_scan_id[0]
        if sid is None:
            messagebox.showinfo("Verify", "Chưa có phiên scan. Chạy scan trước.")
            return
        result_box.insert(tk.END, f"\n\n--- verify-scan (scan_id={sid}) — có thể chậm nếu bật LLM ---\n")
        result_box.see(tk.END)
        win.update_idletasks()
        code, so, se = _run_cli(["verify-scan", "--scan-id", str(sid), "--min-confidence", "low"])
        result_box.insert(tk.END, so)
        if se:
            result_box.insert(tk.END, "\n--- stderr ---\n" + se)
        result_box.insert(tk.END, f"\n(Mã thoát verify-scan: {code})\n")
        result_box.see(tk.END)
        if code != 0:
            messagebox.showerror("Verify-scan", f"Lỗi (mã {code}). Xem log dưới.")

    def verify_one_finding() -> None:
        raw = finding_id_var.get().strip()
        if not raw.isdigit():
            messagebox.showwarning("Verify", "Nhập số ID finding (ví dụ 61).")
            return
        fid = int(raw)
        result_box.insert(tk.END, f"\n\n--- verify --finding-id {fid} ---\n")
        result_box.see(tk.END)
        win.update_idletasks()
        code, so, se = _run_cli(["verify", "--finding-id", str(fid)])
        result_box.insert(tk.END, so)
        if se:
            result_box.insert(tk.END, "\n--- stderr ---\n" + se)
        result_box.insert(tk.END, f"\n(Mã thoát verify: {code})\n")
        result_box.see(tk.END)
        if code != 0:
            messagebox.showerror("Verify", f"Lỗi (mã {code}). Kiểm tra ID có trong DB.")

    btn_verify_all.configure(command=verify_all_session)
    btn_verify_one.configure(command=verify_one_finding)

    def run_scan() -> None:
        raw = path_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning("Thiếu đường dẫn", "Hãy dán đường dẫn hoặc bấm Chọn thư mục / file.")
            return
        p = Path(raw)
        if not p.exists():
            messagebox.showerror("Không tồn tại", f"Không thấy đường dẫn:\n{raw}")
            return

        out.delete("1.0", tk.END)
        result_box.delete("1.0", tk.END)
        out.insert(tk.END, f"Đang scan: {p.resolve()}\n")
        win.update_idletasks()

        code, so, se = _run_scan(str(p.resolve()))
        out.insert(tk.END, so)
        if se:
            out.insert(tk.END, "\n--- stderr ---\n" + se)
        out.insert(tk.END, f"\n(Mã thoát: {code})\n")

        last_json_path[0] = None
        last_scan_id[0] = None
        _set_verify_enabled(False)
        if code != 0:
            messagebox.showerror("Scan lỗi", f"Mã thoát {code}. Xem log phía trên.")
            result_box.insert(tk.END, "Scan không thành công — không có báo cáo JSON.")
            return

        jpath = _extract_json_path(so)
        if not jpath:
            result_box.insert(
                tk.END,
                "Không parse được đường dẫn JSON từ log. Xem log phía trên.\n\n" + so,
            )
            messagebox.showwarning("Thiếu JSON", "Không tìm thấy dòng JSON: trong output.")
            return

        jp = Path(jpath)
        last_json_path[0] = str(jp)
        if not jp.is_file():
            result_box.insert(tk.END, f"Không đọc được file: {jpath}")
            messagebox.showerror("Lỗi", f"Không thấy file:\n{jpath}")
            return

        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            result_box.insert(tk.END, f"Lỗi đọc JSON: {e}")
            messagebox.showerror("Lỗi JSON", str(e))
            return

        report = _format_report(data)
        result_box.insert(tk.END, report)

        scan = data.get("scan") or {}
        sid = scan.get("id")
        if sid is not None:
            last_scan_id[0] = int(sid)
            _set_verify_enabled(True)
        else:
            _set_verify_enabled(False)

    ttk.Button(btns, text="Chạy scan", command=run_scan).pack(side=tk.RIGHT)

    win.mainloop()


if __name__ == "__main__":
    main()
