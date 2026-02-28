import csv
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

from models import (
    AllocationResult,
    AllocationStatus,
    ExamHall,
    Student,
)
# from reasoning_engine import AllocationSolver
# from rule_engine import RuleEngine


# ═══════════════════════════════════════════════════════════════════════════
#  Colour Palette & Styling Constants
# ═══════════════════════════════════════════════════════════════════════════

BG_MAIN      = "#1e1e2e"
BG_SIDEBAR   = "#181825"
BG_CARD      = "#27273a"
BG_ENTRY     = "#313244"
FG_TEXT       = "#cdd6f4"
FG_DIM        = "#a6adc8"
FG_TITLE      = "#cba6f7"
ACCENT        = "#89b4fa"
ACCENT_HOVER  = "#74c7ec"
GREEN         = "#a6e3a1"
RED           = "#f38ba8"
YELLOW        = "#f9e2af"
FONT_FAMILY   = "Segoe UI"
FONT_MONO     = "Consolas"


# ═══════════════════════════════════════════════════════════════════════════
#  Helper: CSV Loader
# ═══════════════════════════════════════════════════════════════════════════

def load_students_csv(path: str) -> List[Student]:
    students = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            students.append(Student.from_csv_row(row))
    return students


def load_halls_csv(path: str) -> List[ExamHall]:
    halls = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            halls.append(ExamHall.from_csv_row(row))
    return halls


# ═══════════════════════════════════════════════════════════════════════════
#  Main Application Window
# ═══════════════════════════════════════════════════════════════════════════

class ExamAllocatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Intelligent Exam Hall Allocation & Conflict Resolution System")
        self.geometry("1280x780")
        self.minsize(1100, 650)
        self.configure(bg=BG_MAIN)
        self.resizable(True, True)

        # --- State ---
        self.students: List[Student] = []
        self.halls: List[ExamHall] = []
        self.results: List[AllocationResult] = []
        self.rule_engine = RuleEngine()

        # --- Build UI ---
        self._build_sidebar()
        self._build_main_area()
        self._update_status("Ready.  Import Students and Halls CSV files to begin.")

    # ═══════════════════════════════════════════════════════════════════════
    #  Sidebar
    # ═══════════════════════════════════════════════════════════════════════

    def _build_sidebar(self):
        self.sidebar = tk.Frame(self, bg=BG_SIDEBAR, width=260)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # Logo / title
        tk.Label(
            self.sidebar, text="🎓 Exam Hall\nAllocation System",
            bg=BG_SIDEBAR, fg=FG_TITLE,
            font=(FONT_FAMILY, 15, "bold"), justify=tk.CENTER,
        ).pack(pady=(28, 8))

        tk.Label(
            self.sidebar, text="KRR-Based Intelligent Engine",
            bg=BG_SIDEBAR, fg=FG_DIM,
            font=(FONT_FAMILY, 9), justify=tk.CENTER,
        ).pack(pady=(0, 24))

        sep = tk.Frame(self.sidebar, bg=BG_CARD, height=2)
        sep.pack(fill=tk.X, padx=20, pady=4)

        # Buttons
        btn_defs = [
            ("📂  Import Students CSV", self._import_students),
            ("🏛  Import Halls CSV",     self._import_halls),
            ("📜  Define / View Rules",  self._show_rules_dialog),
            ("⚙  Run Allocation",       self._run_allocation),
            ("⚠  View Conflict Report", self._show_conflict_report),
        ]
        for text, cmd in btn_defs:
            b = tk.Button(
                self.sidebar, text=text, command=cmd,
                bg=BG_CARD, fg=FG_TEXT, activebackground=ACCENT,
                activeforeground="#000", font=(FONT_FAMILY, 11),
                relief=tk.FLAT, cursor="hand2", anchor="w", padx=18, pady=10,
            )
            b.pack(fill=tk.X, padx=16, pady=5)
            b.bind("<Enter>", lambda e, btn=b: btn.config(bg=ACCENT, fg="#000"))
            b.bind("<Leave>", lambda e, btn=b: btn.config(bg=BG_CARD, fg=FG_TEXT))

        # Spacer
        tk.Frame(self.sidebar, bg=BG_SIDEBAR).pack(fill=tk.BOTH, expand=True)

        # Status indicators
        self.lbl_students_count = tk.Label(
            self.sidebar, text="Students loaded: 0",
            bg=BG_SIDEBAR, fg=FG_DIM, font=(FONT_FAMILY, 9),
        )
        self.lbl_students_count.pack(pady=(2, 0), padx=20, anchor="w")

        self.lbl_halls_count = tk.Label(
            self.sidebar, text="Halls loaded: 0",
            bg=BG_SIDEBAR, fg=FG_DIM, font=(FONT_FAMILY, 9),
        )
        self.lbl_halls_count.pack(pady=(2, 12), padx=20, anchor="w")

    # ═══════════════════════════════════════════════════════════════════════
    #  Main content area
    # ═══════════════════════════════════════════════════════════════════════

    def _build_main_area(self):
        self.main_area = tk.Frame(self, bg=BG_MAIN)
        self.main_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Status bar at top
        self.status_frame = tk.Frame(self.main_area, bg=BG_CARD, height=40)
        self.status_frame.pack(fill=tk.X, padx=16, pady=(16, 0))
        self.status_frame.pack_propagate(False)

        self.lbl_status = tk.Label(
            self.status_frame, text="", bg=BG_CARD, fg=FG_TEXT,
            font=(FONT_FAMILY, 11), anchor="w", padx=14,
        )
        self.lbl_status.pack(fill=tk.BOTH, expand=True)

        # Statistics cards row
        self.stats_frame = tk.Frame(self.main_area, bg=BG_MAIN)
        self.stats_frame.pack(fill=tk.X, padx=16, pady=(12, 0))

        self.stat_cards = {}
        for label, key, color in [
            ("Total Students", "total", ACCENT),
            ("Allocated", "allocated", GREEN),
            ("Conflicts", "conflicts", RED),
            ("Halls Used", "halls_used", YELLOW),
        ]:
            card = tk.Frame(self.stats_frame, bg=BG_CARD, padx=18, pady=10)
            card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
            tk.Label(card, text=label, bg=BG_CARD, fg=FG_DIM,
                     font=(FONT_FAMILY, 9)).pack(anchor="w")
            val = tk.Label(card, text="—", bg=BG_CARD, fg=color,
                           font=(FONT_FAMILY, 20, "bold"))
            val.pack(anchor="w")
            self.stat_cards[key] = val

        # Results table
        table_frame = tk.Frame(self.main_area, bg=BG_MAIN)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(12, 4))

        columns = ("roll", "dept", "gender", "hall", "seat", "status")
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="browse",
        )
        headings = {
            "roll": "Roll No.", "dept": "Department", "gender": "Gender",
            "hall": "Assigned Hall", "seat": "Seat #", "status": "Status",
        }
        col_widths = {
            "roll": 90, "dept": 130, "gender": 80,
            "hall": 140, "seat": 80, "status": 120,
        }
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=col_widths[col], anchor=tk.CENTER)

        # Style the treeview
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview",
                        background=BG_CARD, foreground=FG_TEXT,
                        fieldbackground=BG_CARD, rowheight=28,
                        font=(FONT_FAMILY, 10))
        style.configure("Treeview.Heading",
                        background=BG_ENTRY, foreground=FG_TITLE,
                        font=(FONT_FAMILY, 10, "bold"))
        style.map("Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "#000")])

        self.tree.tag_configure("allocated", foreground=GREEN)
        self.tree.tag_configure("conflict", foreground=RED)

        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)

        # Detail panel at bottom
        self.detail_frame = tk.Frame(self.main_area, bg=BG_CARD, height=210)
        self.detail_frame.pack(fill=tk.X, padx=16, pady=(4, 16))
        self.detail_frame.pack_propagate(False)

        tk.Label(
            self.detail_frame, text="  Conflict / Allocation Details",
            bg=BG_CARD, fg=FG_TITLE, font=(FONT_FAMILY, 11, "bold"),
            anchor="w",
        ).pack(fill=tk.X, padx=8, pady=(8, 2))

        self.detail_text = tk.Text(
            self.detail_frame, bg=BG_ENTRY, fg=FG_TEXT, wrap=tk.WORD,
            font=(FONT_MONO, 10), relief=tk.FLAT, padx=12, pady=8,
            insertbackground=FG_TEXT,
        )
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.detail_text.config(state=tk.DISABLED)

    # ═══════════════════════════════════════════════════════════════════════
    #  Actions
    # ═══════════════════════════════════════════════════════════════════════

    def _import_students(self):
        path = filedialog.askopenfilename(
            title="Select Students CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.students = load_students_csv(path)
            self.lbl_students_count.config(text=f"Students loaded: {len(self.students)}")
            self._update_status(
                f"✔ Imported {len(self.students)} students from {os.path.basename(path)}."
            )
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to load students CSV.\n\n{e}")

    def _import_halls(self):
        path = filedialog.askopenfilename(
            title="Select Exam Halls CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.halls = load_halls_csv(path)
            self.lbl_halls_count.config(text=f"Halls loaded: {len(self.halls)}")
            self._update_status(
                f"✔ Imported {len(self.halls)} halls from {os.path.basename(path)}."
            )
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to load halls CSV.\n\n{e}")

    def _run_allocation(self):
        if not self.students:
            messagebox.showwarning("No Data", "Import students CSV first.")
            return
        if not self.halls:
            messagebox.showwarning("No Data", "Import exam halls CSV first.")
            return

        solver = AllocationSolver(self.rule_engine)
        self.results = solver.solve(self.students, self.halls)
        self._populate_table()

        allocated = sum(1 for r in self.results if r.status == AllocationStatus.ALLOCATED)
        conflicts = sum(1 for r in self.results if r.status == AllocationStatus.CONFLICT)
        halls_used = len({r.assigned_hall for r in self.results if r.assigned_hall})

        self.stat_cards["total"].config(text=str(len(self.results)))
        self.stat_cards["allocated"].config(text=str(allocated))
        self.stat_cards["conflicts"].config(text=str(conflicts))
        self.stat_cards["halls_used"].config(text=str(halls_used))

        if conflicts:
            self._update_status(
                f"⚠ Allocation complete — {allocated} allocated, {conflicts} conflict(s) detected.",
                color=RED,
            )
        else:
            self._update_status(
                f"✔ Allocation successful — all {allocated} students assigned.",
                color=GREEN,
            )

    def _show_rules_dialog(self):
        RulesDialog(self, self.rule_engine)

    def _show_conflict_report(self):
        conflicts = [r for r in self.results if r.status == AllocationStatus.CONFLICT]
        if not conflicts:
            messagebox.showinfo("No Conflicts", "No conflicts to report.  Run allocation first.")
            return
        ConflictReportWindow(self, conflicts)

    # ═══════════════════════════════════════════════════════════════════════
    #  Table Population & Selection
    # ═══════════════════════════════════════════════════════════════════════

    def _populate_table(self):
        self.tree.delete(*self.tree.get_children())
        for r in self.results:
            tag = "allocated" if r.status == AllocationStatus.ALLOCATED else "conflict"
            self.tree.insert("", tk.END, values=(
                r.student.roll,
                r.student.department,
                r.student.gender.value,
                r.assigned_hall or "—",
                r.seat_number if r.seat_number else "—",
                r.status.value,
            ), tags=(tag,))

    def _on_row_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        roll = int(item["values"][0])
        result = next((r for r in self.results if r.student.roll == roll), None)
        if not result:
            return

        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)

        if result.status == AllocationStatus.ALLOCATED:
            self.detail_text.insert(tk.END,
                f"✔ Student {result.student.roll} successfully allocated.\n\n"
                f"   Hall : {result.assigned_hall}\n"
                f"   Seat : {result.seat_number}\n"
                f"   Dept : {result.student.department}\n"
                f"   Gender: {result.student.gender.value}\n"
                f"   Disabled: {'Yes' if result.student.disabled else 'No'}\n"
            )
        else:
            self.detail_text.insert(tk.END, result.explanation)
            if result.suggestions:
                self.detail_text.insert(tk.END, "\n\n💡 Resolution Suggestions:\n")
                for i, s in enumerate(result.suggestions, 1):
                    self.detail_text.insert(tk.END, f"  {i}. {s}\n")

        self.detail_text.config(state=tk.DISABLED)

    # ═══════════════════════════════════════════════════════════════════════
    #  Helpers
    # ═══════════════════════════════════════════════════════════════════════

    def _update_status(self, text: str, color: str = FG_TEXT):
        self.lbl_status.config(text=text, fg=color)


# ═══════════════════════════════════════════════════════════════════════════
#  Rules Viewer / Editor Dialog
# ═══════════════════════════════════════════════════════════════════════════

class RulesDialog(tk.Toplevel):
    def __init__(self, parent, rule_engine: RuleEngine):
        super().__init__(parent)
        self.title("Constraint Rules — View & Toggle")
        self.geometry("640x500")
        self.configure(bg=BG_MAIN)
        self.resizable(False, False)
        self.grab_set()

        self.rule_engine = rule_engine
        self.check_vars = {}

        tk.Label(
            self, text="📜 Knowledge Base — Constraint Rules",
            bg=BG_MAIN, fg=FG_TITLE, font=(FONT_FAMILY, 14, "bold"),
        ).pack(pady=(18, 6))

        tk.Label(
            self, text="Toggle rules on/off. Disabled rules are ignored during allocation.",
            bg=BG_MAIN, fg=FG_DIM, font=(FONT_FAMILY, 9),
        ).pack(pady=(0, 14))

        container = tk.Frame(self, bg=BG_MAIN)
        container.pack(fill=tk.BOTH, expand=True, padx=20)

        descriptions = {
            "R1": "A hall cannot exceed its seating capacity.",
            "R2": "A student's gender must match the hall's allowed-gender policy.",
            "R3": "If department mixing is not allowed, only one department per hall.",
            "R4": "Disabled students must be assigned to ground-floor halls.",
            "R5": "No two students with consecutive roll numbers on adjacent seats (anti-cheating).",
        }

        for rid, name, enabled in self.rule_engine.get_rules_info():
            card = tk.Frame(container, bg=BG_CARD, padx=14, pady=10)
            card.pack(fill=tk.X, pady=4)

            var = tk.BooleanVar(value=enabled)
            self.check_vars[rid] = var

            cb = tk.Checkbutton(
                card, variable=var, bg=BG_CARD, fg=FG_TEXT,
                selectcolor=BG_ENTRY, activebackground=BG_CARD,
                activeforeground=FG_TEXT, font=(FONT_FAMILY, 11, "bold"),
                text=f"[{rid}]  {name}",
                command=lambda r=rid, v=var: self.rule_engine.set_enabled(r, v.get()),
            )
            cb.pack(anchor="w")

            desc = descriptions.get(rid, "")
            if desc:
                tk.Label(
                    card, text=f"    {desc}", bg=BG_CARD, fg=FG_DIM,
                    font=(FONT_FAMILY, 9), wraplength=560, justify=tk.LEFT,
                ).pack(anchor="w", padx=(24, 0))

        tk.Button(
            self, text="Close", command=self.destroy,
            bg=ACCENT, fg="#000", font=(FONT_FAMILY, 11, "bold"),
            relief=tk.FLAT, padx=30, pady=6, cursor="hand2",
        ).pack(pady=16)


# ═══════════════════════════════════════════════════════════════════════════
#  Conflict Report Window
# ═══════════════════════════════════════════════════════════════════════════

class ConflictReportWindow(tk.Toplevel):
    def __init__(self, parent, conflicts: List[AllocationResult]):
        super().__init__(parent)
        self.title(f"Conflict Report — {len(conflicts)} Conflict(s)")
        self.geometry("900x620")
        self.configure(bg=BG_MAIN)
        self.resizable(True, True)

        self.conflicts = conflicts

        # Header
        tk.Label(
            self, text=f"⚠ {len(conflicts)} Student(s) Could Not Be Allocated",
            bg=BG_MAIN, fg=RED, font=(FONT_FAMILY, 15, "bold"),
        ).pack(pady=(16, 4))

        # Paned window: left = list, right = details
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=BG_MAIN,
                               sashwidth=6, sashrelief=tk.FLAT)
        paned.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # Left: conflict list
        left = tk.Frame(paned, bg=BG_CARD)
        paned.add(left, width=260)

        tk.Label(left, text="Conflicting Students", bg=BG_CARD, fg=FG_TITLE,
                 font=(FONT_FAMILY, 11, "bold")).pack(pady=(10, 4), padx=8, anchor="w")

        self.conflict_listbox = tk.Listbox(
            left, bg=BG_ENTRY, fg=FG_TEXT, font=(FONT_FAMILY, 10),
            selectbackground=ACCENT, selectforeground="#000",
            relief=tk.FLAT, activestyle="none",
        )
        self.conflict_listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        for c in self.conflicts:
            self.conflict_listbox.insert(
                tk.END,
                f"Roll {c.student.roll}  |  {c.student.department}  |  {c.student.gender.value}"
            )

        self.conflict_listbox.bind("<<ListboxSelect>>", self._on_select)

        # Right: details
        right = tk.Frame(paned, bg=BG_CARD)
        paned.add(right)

        tk.Label(right, text="Detailed Reasoning & Suggestions", bg=BG_CARD,
                 fg=FG_TITLE, font=(FONT_FAMILY, 11, "bold")).pack(
            pady=(10, 4), padx=8, anchor="w")

        self.detail_text = tk.Text(
            right, bg=BG_ENTRY, fg=FG_TEXT, wrap=tk.WORD,
            font=(FONT_MONO, 10), relief=tk.FLAT, padx=12, pady=8,
            insertbackground=FG_TEXT,
        )
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.detail_text.config(state=tk.DISABLED)

        # Auto-select first
        if self.conflicts:
            self.conflict_listbox.selection_set(0)
            self._show_detail(0)

    def _on_select(self, _event):
        sel = self.conflict_listbox.curselection()
        if sel:
            self._show_detail(sel[0])

    def _show_detail(self, idx: int):
        c = self.conflicts[idx]
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)

        self.detail_text.insert(tk.END, c.explanation)

        if c.suggestions:
            self.detail_text.insert(tk.END, "\n\n" + "=" * 50)
            self.detail_text.insert(tk.END, "\n💡 RESOLUTION SUGGESTIONS\n")
            self.detail_text.insert(tk.END, "=" * 50 + "\n\n")
            for i, s in enumerate(c.suggestions, 1):
                self.detail_text.insert(tk.END, f"  {i}. {s}\n\n")

        self.detail_text.config(state=tk.DISABLED)
