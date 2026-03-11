"""Tkinter GUI for AI Email Router."""

import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path

from email_classifier import classify_emails
from openai import OpenAI
from config import OPENAI_API_KEY, TELEGRAM_BOT_TOKEN


def send_to_telegram(bot_token: str, recipient: str, content: str) -> bool:
    """Send message to Telegram. Returns True if success."""
    try:
        import requests
        chat_id = recipient.strip()
        if not chat_id.lstrip("-").isdigit():
            if not chat_id.startswith("@"):
                chat_id = "@" + chat_id
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        resp = requests.post(url, json={"chat_id": chat_id, "text": content})
        return resp.status_code == 200
    except Exception:
        return False


def create_ui():
    """Create and run the main window."""
    root = tk.Tk()
    root.title("AI Email Router")
    root.geometry("700x650")
    root.minsize(500, 400)

    # API Key
    api_frame = ttk.Frame(root, padding=10)
    api_frame.pack(fill=tk.X)
    ttk.Label(api_frame, text="OpenAI API Key:").pack(side=tk.LEFT)
    api_key_var = tk.StringVar(value=OPENAI_API_KEY)
    api_entry = ttk.Entry(api_frame, textvariable=api_key_var, show="*", width=50)
    api_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

    # Email Input
    ttk.Label(root, text="Email Inputs:", font=("", 10, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 2))
    email_input = scrolledtext.ScrolledText(root, height=10, wrap=tk.WORD, font=("Consolas", 10))
    email_input.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))
    email_input.insert(tk.END, "Hello, I want to buy your product.\nMy account is not working.\nCan you send me pricing?\nThis is a marketing offer.")

    # Buttons
    btn_frame = ttk.Frame(root, padding=10)
    btn_frame.pack(fill=tk.X)

    results_var = tk.StringVar(value="")
    results_list = []

    def analyze():
        api_key = (api_key_var.get() or OPENAI_API_KEY).strip()
        if not api_key:
            messagebox.showerror(
                "Error",
                "Chưa có OpenAI API key.\n\nPaste key vào ô OpenAI API Key, hoặc đặt biến môi trường OPENAI_API_KEY.",
            )
            return

        text = email_input.get("1.0", tk.END)
        emails = [line.strip() for line in text.split("\n") if line.strip()]

        if not emails:
            messagebox.showwarning("Warning", "No emails to analyze.")
            return

        try:
            client = OpenAI(api_key=api_key)
            results_list.clear()
            results_list.extend(classify_emails(client, emails))

            # Display
            lines = []
            for i, r in enumerate(results_list, 1):
                lines.append(f"Email {i} → {r['category'].title()}")

            results_var.set("\n".join(lines))

            # Save JSON
            output_path = Path("email_classification_results.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results_list, f, indent=2, ensure_ascii=False)

            messagebox.showinfo("Done", f"Classified {len(results_list)} emails.\nSaved to {output_path}")

        except Exception as e:
            messagebox.showerror("Error", str(e))

    ttk.Button(btn_frame, text="Analyze Emails", command=analyze).pack(side=tk.LEFT, padx=(0, 5))

    def send_telegram():
        dialog = tk.Toplevel(root)
        dialog.title("Send to Telegram")
        dialog.geometry("420x220")
        ttk.Label(dialog, text="Bot Token (lấy từ @BotFather):").pack(anchor=tk.W, padx=10, pady=2)
        token_entry = ttk.Entry(dialog, width=50, show="*")
        token_entry.pack(fill=tk.X, padx=10, pady=2)
        token_entry.insert(0, TELEGRAM_BOT_TOKEN)
        ttk.Label(dialog, text="Nội dung:").pack(anchor=tk.W, padx=10, pady=(8, 2))
        content_entry = ttk.Entry(dialog, width=50)
        content_entry.pack(fill=tk.X, padx=10, pady=2)
        content_entry.insert(0, "Hey you have email")
        ttk.Label(dialog, text="Telegram người nhận:").pack(anchor=tk.W, padx=10, pady=(8, 2))
        recipient_entry = ttk.Entry(dialog, width=50)
        recipient_entry.pack(fill=tk.X, padx=10, pady=2)
        recipient_entry.insert(0, "ydang")

        def do_send():
            token = token_entry.get().strip()
            content = content_entry.get().strip()
            recipient = recipient_entry.get().strip()
            if not token:
                messagebox.showerror("Error", "Nhập Bot Token (tạo bot qua @BotFather).")
                return
            if not content:
                messagebox.showerror("Error", "Nhập nội dung.")
                return
            if not recipient:
                messagebox.showerror("Error", "Nhập Telegram người nhận.")
                return
            if send_to_telegram(token, recipient, content):
                messagebox.showinfo("Done", "Đã gửi.")
                dialog.destroy()
            else:
                messagebox.showerror("Error", "Gửi thất bại. Kiểm tra tên người nhận và đã /start bot chưa.")

        ttk.Button(dialog, text="Send", command=do_send).pack(pady=10)

    ttk.Button(btn_frame, text="Send to Telegram", command=send_telegram).pack(side=tk.LEFT)

    # Output
    ttk.Label(root, text="Classification Results:", font=("", 10, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 2))
    results_output = scrolledtext.ScrolledText(root, height=8, wrap=tk.WORD, font=("Consolas", 10))
    results_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    def update_results_display(*args):
        results_output.delete("1.0", tk.END)
        results_output.insert(tk.END, results_var.get())

    results_var.trace_add("write", update_results_display)

    root.mainloop()


if __name__ == "__main__":
    create_ui()
