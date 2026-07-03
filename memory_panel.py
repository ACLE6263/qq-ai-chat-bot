#!/usr/bin/env python3
"""Memory Panel — Desktop GUI for controlling bot conversation memory.

Run alongside the bot:  py memory_panel.py
Communicates with the bot via its built-in HTTP API (port from .env).
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.error import URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BOT_HOST = "127.0.0.1"
BOT_PORT = 8090  # same as .env PORT
BASE_URL = f"http://{BOT_HOST}:{BOT_PORT}"
REFRESH_MS = 3000  # auto-refresh interval


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
def _api(method: str, path: str, data: dict | None = None) -> dict:
    """Call the bot API. Raises URLError on connection failure."""
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------
class MemoryPanel(tk.Tk):
    """Main GUI window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Bot Memory Panel")
        self.geometry("540x420")
        self.resizable(True, True)
        self.configure(padx=12, pady=12)

        # Data
        self._sessions: list[dict] = []
        self._selected_sid: str = ""

        # -- Build UI --
        self._build_widgets()

        # Start refresh loop
        self._refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_widgets(self) -> None:
        """Lay out all widgets."""
        # Top: status bar
        self._status_var = tk.StringVar(value="Connecting...")
        status_bar = ttk.Label(
            self, textvariable=self._status_var, relief=tk.SUNKEN, anchor=tk.W
        )
        status_bar.pack(fill=tk.X, pady=(0, 8))

        # Main area: left panel (session list) + right panel (controls)
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # -- Left: session list --
        left = ttk.LabelFrame(main_frame, text="Active Sessions", padding=4)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        self._listbox = tk.Listbox(left, width=18, exportselection=False)
        self._listbox.pack(fill=tk.BOTH, expand=True)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        # -- Right: controls --
        right = ttk.Frame(main_frame, padding=4)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Session info
        info_frame = ttk.LabelFrame(right, text="Session Info", padding=6)
        info_frame.pack(fill=tk.X, pady=(0, 8))

        self._info_id = ttk.Label(info_frame, text="Session ID: —")
        self._info_id.pack(anchor=tk.W)
        self._info_msgs = ttk.Label(info_frame, text="Messages: —")
        self._info_msgs.pack(anchor=tk.W)
        self._info_tokens = ttk.Label(info_frame, text="Est. Tokens: —")
        self._info_tokens.pack(anchor=tk.W)

        # Memory controls
        mem_frame = ttk.LabelFrame(right, text="Memory Control", padding=6)
        mem_frame.pack(fill=tk.X, pady=(0, 8))

        # -- Unlimited toggle --
        self._unlimited_var = tk.BooleanVar(value=False)
        self._unlimited_cb = ttk.Checkbutton(
            mem_frame,
            text="Unlimited (no truncation)",
            variable=self._unlimited_var,
            command=self._on_unlimited_toggle,
        )
        self._unlimited_cb.pack(anchor=tk.W, pady=(0, 4))

        # -- Turns input row --
        turns_row = ttk.Frame(mem_frame)
        turns_row.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(turns_row, text="Turns:").pack(side=tk.LEFT)
        self._turns_var = tk.StringVar(value="20")
        self._turns_entry = ttk.Entry(
            turns_row, textvariable=self._turns_var, width=6, state=tk.NORMAL
        )
        self._turns_entry.pack(side=tk.LEFT, padx=4)

        self._apply_btn = ttk.Button(
            turns_row, text="Apply", command=self._on_apply
        )
        self._apply_btn.pack(side=tk.LEFT, padx=2)

        # -- Clear button --
        self._clear_btn = ttk.Button(
            mem_frame,
            text="Clear Memory (Forget All)",
            command=self._on_clear,
        )
        self._clear_btn.pack(fill=tk.X)

        # -- QQ commands reference --
        cmd_frame = ttk.LabelFrame(right, text="QQ Commands", padding=6)
        cmd_frame.pack(fill=tk.X, pady=(8, 4))

        commands = (
            "/memory          — show current setting\n"
            "/memory <N>   — set memory to N turns\n"
            "/memory max   — unlimited (no truncation)\n"
            "/memory default — reset to config default\n"
            "/reset              — clear all conversation history"
        )
        ttk.Label(
            cmd_frame,
            text=commands,
            font=("Consolas", 9),
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        # Refresh hint
        ttk.Label(
            right,
            text=f"Auto-refreshes every {REFRESH_MS // 1000}s",
            foreground="gray",
        ).pack(anchor=tk.SE)

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        """Poll the bot API and update the UI."""
        try:
            data = _api("GET", "/api/sessions")
            self._sessions = data.get("sessions", [])
            self._status_var.set(
                f"Connected | {len(self._sessions)} active session(s) | Default: {data.get('default_turns', '?')} turns"
            )
        except URLError:
            self._status_var.set("Disconnected — bot not running?")
            self._sessions = []
        except Exception as e:
            self._status_var.set(f"Error: {e}")

        self._populate_listbox()
        self.after(REFRESH_MS, self._refresh)

    def _populate_listbox(self) -> None:
        """Rebuild the session listbox, preserving selection."""
        selected = (
            self._selected_sid
            if self._selected_sid
            else (self._listbox.curselection() and self._listbox.get(self._listbox.curselection()[0]).split("  ")[0])
        )
        self._listbox.delete(0, tk.END)

        for s in self._sessions:
            sid = s["session_id"]
            icon = "∞" if s["is_unlimited"] else str(s["max_turns"])
            label = f"{sid}  [{icon}]"
            self._listbox.insert(tk.END, label)

        # Re-select
        if selected:
            for i, s in enumerate(self._sessions):
                if s["session_id"] == selected:
                    self._listbox.selection_set(i)
                    self._listbox.see(i)
                    self._show_session(s)
                    break

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_select(self, _event: tk.Event | None = None) -> None:
        idx = self._listbox.curselection()
        if not idx:
            return
        sid = self._listbox.get(idx[0]).split("  ")[0]
        for s in self._sessions:
            if s["session_id"] == sid:
                self._selected_sid = sid
                self._show_session(s)
                break

    def _show_session(self, s: dict) -> None:
        """Fill the right panel with session data."""
        self._info_id.config(text=f"Session ID: {s['session_id']}")
        self._info_msgs.config(text=f"Messages: {s['message_count']} ({s['turn_count']} turns)")
        self._info_tokens.config(text=f"Est. Tokens: {s['total_tokens']}")

        if s["is_unlimited"]:
            self._unlimited_var.set(True)
            self._turns_entry.config(state=tk.DISABLED)
        else:
            self._unlimited_var.set(False)
            self._turns_entry.config(state=tk.NORMAL)
            self._turns_var.set(str(s["max_turns"]))

    def _on_unlimited_toggle(self) -> None:
        if self._unlimited_var.get():
            self._turns_entry.config(state=tk.DISABLED)
        else:
            self._turns_entry.config(state=tk.NORMAL)

    def _on_apply(self) -> None:
        sid = self._selected_sid
        if not sid:
            messagebox.showwarning("No Session", "Select a session first.")
            return

        try:
            if self._unlimited_var.get():
                result = _api("POST", f"/api/sessions/{sid}/memory", {"turns": "unlimited"})
            else:
                n = int(self._turns_var.get())
                if n <= 0:
                    messagebox.showwarning("Bad Value", "Turns must be positive.")
                    return
                result = _api("POST", f"/api/sessions/{sid}/memory", {"turns": n})
            messagebox.showinfo("Done", result.get("message", "OK"))
            self._refresh()
        except URLError:
            messagebox.showerror("Error", "Cannot connect to bot.")
        except ValueError:
            messagebox.showwarning("Bad Value", "Enter a number for turns.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_clear(self) -> None:
        sid = self._selected_sid
        if not sid:
            messagebox.showwarning("No Session", "Select a session first.")
            return

        if not messagebox.askyesno("Confirm", f"Clear ALL memory for session {sid}?"):
            return

        try:
            _api("DELETE", f"/api/sessions/{sid}")
            messagebox.showinfo("Cleared", "Memory cleared.")
            self._refresh()
        except URLError:
            messagebox.showerror("Error", "Cannot connect to bot.")
        except Exception as e:
            messagebox.showerror("Error", str(e))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    MemoryPanel().mainloop()
