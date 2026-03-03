import json
import os
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Dict, Any, List, Tuple
from PySide6.QtWidgets import QStyle

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QMessageBox, QComboBox,
    QDateEdit, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFrame, QScrollArea, QProgressBar, QSpacerItem, QSizePolicy
)

DATA_FILE = "data.json"


# --------------------------- Data helpers ---------------------------

def new_id() -> str:
    return uuid.uuid4().hex


def today_iso() -> str:
    return date.today().isoformat()


def parse_iso(d: str) -> date:
    return date.fromisoformat(d)


def fmt_money(x: float) -> str:
    return f"£{x:,.2f}"


def safe_float(s: str) -> Optional[float]:
    if s is None:
        return None
    s = s.strip().replace("£", "").replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def month_key(d: date) -> Tuple[int, int]:
    return (d.year, d.month)


def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        return {
            "starting_balance": 0.0,
            "jobs": [],
            "payments": [],
            "expenses": [],
            "wants": []
        }
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Backward-compatible defaults
    data.setdefault("starting_balance", 0.0)
    data.setdefault("jobs", [])
    data.setdefault("payments", [])
    data.setdefault("expenses", [])
    data.setdefault("wants", [])
    return data


def save_data(data: Dict[str, Any]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# --------------------------- Finance calculations ---------------------------

class Finance:
    @staticmethod
    def total_income(data: Dict[str, Any]) -> float:
        return float(sum(float(p.get("amount", 0.0)) for p in data["payments"]))

    @staticmethod
    def total_expenses(data: Dict[str, Any]) -> float:
        return float(sum(float(e.get("amount", 0.0)) for e in data["expenses"]))

    @staticmethod
    def balance(data: Dict[str, Any]) -> float:
        return float(data.get("starting_balance", 0.0)) + Finance.total_income(data) - Finance.total_expenses(data)

    @staticmethod
    def totals_this_month(data: Dict[str, Any], now: Optional[date] = None) -> Tuple[float, float]:
        now = now or date.today()
        mk = month_key(now)

        inc = 0.0
        for p in data["payments"]:
            try:
                d = parse_iso(p.get("date", today_iso()))
            except Exception:
                continue
            if month_key(d) == mk:
                inc += float(p.get("amount", 0.0))

        exp = 0.0
        for e in data["expenses"]:
            try:
                d = parse_iso(e.get("date", today_iso()))
            except Exception:
                continue
            if month_key(d) == mk:
                exp += float(e.get("amount", 0.0))

        return inc, exp

    @staticmethod
    def avg_net_per_day(data: Dict[str, Any], window_days: int = 60) -> Optional[float]:
        """
        Estimate avg net/day based on recent history:
        - If enough data in last `window_days`, use that.
        - Otherwise use full span.
        Returns None if not enough history or net/day <= 0.
        """
        dates: List[date] = []

        for p in data["payments"]:
            d = p.get("date")
            if d:
                try:
                    dates.append(parse_iso(d))
                except Exception:
                    pass
        for e in data["expenses"]:
            d = e.get("date")
            if d:
                try:
                    dates.append(parse_iso(d))
                except Exception:
                    pass

        if len(dates) < 2:
            return None

        dates.sort()
        min_d, max_d = dates[0], dates[-1]
        if (max_d - min_d).days < 7:
            return None

        # Prefer recent window if it has enough span
        window_start = max_d.fromordinal(max_d.toordinal() - window_days)
        recent_dates = [d for d in dates if d >= window_start]
        if len(recent_dates) >= 2 and (recent_dates[-1] - recent_dates[0]).days >= 7:
            start, end = recent_dates[0], recent_dates[-1]
        else:
            start, end = min_d, max_d

        span_days = (end - start).days
        if span_days < 7:
            return None

        inc = 0.0
        exp = 0.0

        for p in data["payments"]:
            try:
                d = parse_iso(p.get("date", today_iso()))
            except Exception:
                continue
            if start <= d <= end:
                inc += float(p.get("amount", 0.0))

        for e in data["expenses"]:
            try:
                d = parse_iso(e.get("date", today_iso()))
            except Exception:
                continue
            if start <= d <= end:
                exp += float(e.get("amount", 0.0))

        net = inc - exp
        per_day = net / float(span_days)
        if per_day <= 0:
            return None
        return per_day

    @staticmethod
    def want_remaining(data: Dict[str, Any], want: Dict[str, Any]) -> float:
        if want.get("purchased", False):
            return 0.0
        price = float(want.get("price", 0.0))
        remaining = price - Finance.balance(data)
        return max(0.0, remaining)

    @staticmethod
    def want_progress(data: Dict[str, Any], want: Dict[str, Any]) -> float:
        """
        Returns 0..1
        """
        if want.get("purchased", False):
            return 1.0
        price = float(want.get("price", 0.0))
        if price <= 0:
            return 0.0
        bal = Finance.balance(data)
        pct = bal / price
        return max(0.0, min(1.0, pct))

    @staticmethod
    def want_days_away(data: Dict[str, Any], want: Dict[str, Any]) -> Optional[float]:
        remaining = Finance.want_remaining(data, want)
        if remaining <= 0:
            return 0.0
        net_per_day = Finance.avg_net_per_day(data)
        if net_per_day is None or net_per_day <= 0:
            return None
        return remaining / net_per_day


# --------------------------- UI polish: dark theme ---------------------------

def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")

    dark = QPalette()
    dark.setColor(QPalette.Window, QColor(30, 30, 30))
    dark.setColor(QPalette.WindowText, Qt.white)
    dark.setColor(QPalette.Base, QColor(22, 22, 22))
    dark.setColor(QPalette.AlternateBase, QColor(35, 35, 35))
    dark.setColor(QPalette.ToolTipBase, Qt.white)
    dark.setColor(QPalette.ToolTipText, Qt.white)
    dark.setColor(QPalette.Text, Qt.white)
    dark.setColor(QPalette.Button, QColor(45, 45, 45))
    dark.setColor(QPalette.ButtonText, Qt.white)
    dark.setColor(QPalette.BrightText, Qt.red)
    dark.setColor(QPalette.Highlight, QColor(90, 140, 255))
    dark.setColor(QPalette.HighlightedText, Qt.black)

    app.setPalette(dark)

    app.setStyleSheet("""
        QWidget { font-size: 12px; }
        QTabWidget::pane { border: 1px solid #2a2a2a; border-radius: 10px; }
        QTabBar::tab { background: #2b2b2b; padding: 8px 14px; border-top-left-radius: 10px; border-top-right-radius: 10px; margin-right: 6px; }
        QTabBar::tab:selected { background: #3a3a3a; }
        QLineEdit, QComboBox, QDateEdit {
            background: #1f1f1f;
            border: 1px solid #3a3a3a;
            border-radius: 8px;
            padding: 8px;
        }
        QPushButton {
            background: #3b3b3b;
            border: 1px solid #4a4a4a;
            border-radius: 10px;
            padding: 8px 12px;
        }
        QPushButton:hover { background: #4a4a4a; }
        QPushButton:pressed { background: #2f2f2f; }
        QTableWidget {
            background: #1f1f1f;
            border: 1px solid #2f2f2f;
            border-radius: 10px;
            gridline-color: #2f2f2f;
        }
        QHeaderView::section {
            background: #2a2a2a;
            padding: 8px;
            border: 1px solid #2f2f2f;
        }
        QProgressBar {
            background: #222;
            border: 1px solid #3a3a3a;
            border-radius: 8px;
            text-align: center;
            height: 18px;
        }
        QProgressBar::chunk {
            background: #5a8cff;
            border-radius: 8px;
        }
    """)


# --------------------------- Widgets ---------------------------

class Card(QFrame):
    def __init__(self, title: str = "", subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("""
            QFrame {
                background: #242424;
                border: 1px solid #2f2f2f;
                border-radius: 14px;
            }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        if title:
            t = QLabel(title)
            t.setStyleSheet("font-size: 16px; font-weight: 700;")
            lay.addWidget(t)

        if subtitle:
            s = QLabel(subtitle)
            s.setStyleSheet("color: #bfbfbf;")
            lay.addWidget(s)

        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        lay.addLayout(self.body)


class WantCard(QFrame):
    def __init__(self, want: Dict[str, Any], on_toggle, on_delete, parent=None):
        super().__init__(parent)
        self.want = want
        self.on_toggle = on_toggle
        self.on_delete = on_delete
        self.anim: Optional[QPropertyAnimation] = None

        self.setStyleSheet("""
            QFrame {
                background: #242424;
                border: 1px solid #2f2f2f;
                border-radius: 14px;
            }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        top = QHBoxLayout()
        self.title = QLabel(want.get("name", ""))
        self.title.setStyleSheet("font-size: 16px; font-weight: 700;")
        top.addWidget(self.title)

        top.addItem(QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.btn_toggle = QPushButton("Purchased ✓" if want.get("purchased", False) else "Mark Purchased")
        self.btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btn_toggle.clicked.connect(lambda: self.on_toggle(self.want))
        top.addWidget(self.btn_toggle)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self.btn_delete.clicked.connect(lambda: self.on_delete(self.want))
        top.addWidget(self.btn_delete)

        lay.addLayout(top)

        self.price = QLabel("")
        self.price.setStyleSheet("color: #bfbfbf;")
        lay.addWidget(self.price)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)  # smoother animation
        self.progress.setValue(0)
        lay.addWidget(self.progress)

        meta = QHBoxLayout()
        self.lbl_remaining = QLabel("")
        self.lbl_remaining.setStyleSheet("font-weight: 600;")
        meta.addWidget(self.lbl_remaining)

        meta.addItem(QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.lbl_days = QLabel("")
        self.lbl_days.setStyleSheet("color: #bfbfbf;")
        meta.addWidget(self.lbl_days)

        lay.addLayout(meta)

        self.lbl_pct = QLabel("")
        self.lbl_pct.setStyleSheet("color: #bfbfbf;")
        lay.addWidget(self.lbl_pct)

    def update_view(self, data: Dict[str, Any]):
        price = float(self.want.get("price", 0.0))
        bal = Finance.balance(data)
        remaining = Finance.want_remaining(data, self.want)
        pct01 = Finance.want_progress(data, self.want)
        pct = pct01 * 100.0
        days = Finance.want_days_away(data, self.want)

        self.price.setText(f"Price: {fmt_money(price)}   •   Balance: {fmt_money(bal)}")

        self.lbl_remaining.setText(f"{fmt_money(remaining)} away" if not self.want.get("purchased", False) else "Completed")
        self.lbl_days.setText("N/A days" if days is None else f"{days:.1f} days")
        self.lbl_pct.setText(f"{pct:.1f}% complete")

        self.btn_toggle.setText("Purchased ✓" if self.want.get("purchased", False) else "Mark Purchased")

        target = int(round(pct01 * 1000.0))
        self._animate_progress(target)

    def _animate_progress(self, target: int):
        if self.anim is not None:
            self.anim.stop()
        self.anim = QPropertyAnimation(self.progress, b"value")
        self.anim.setDuration(450)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.setStartValue(self.progress.value())
        self.anim.setEndValue(target)
        self.anim.start()


# --------------------------- Main Window ---------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Income Tracker")
        self.resize(1100, 680)

        self.data = load_data()

        # Root
        root = QWidget()
        self.setCentralWidget(root)
        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(14, 14, 14, 14)
        root_lay.setSpacing(12)

        # Top summary bar
        self.lbl_summary = QLabel("")
        self.lbl_summary.setStyleSheet("font-size: 14px; font-weight: 700;")
        root_lay.addWidget(self.lbl_summary)

        self.tabs = QTabWidget()
        root_lay.addWidget(self.tabs)

        # Tabs
        self.tab_jobs = QWidget()
        self.tab_payments = QWidget()
        self.tab_expenses = QWidget()
        self.tab_wants = QWidget()

        self.tabs.addTab(self.tab_jobs, "Jobs")
        self.tabs.addTab(self.tab_payments, "Payments")
        self.tabs.addTab(self.tab_expenses, "Expenses")
        self.tabs.addTab(self.tab_wants, "Wants")

        self._build_jobs_tab()
        self._build_payments_tab()
        self._build_expenses_tab()
        self._build_wants_tab()

        self.refresh_all()

    # --------------------------- Common ---------------------------

    def _toast(self, title: str, msg: str):
        QMessageBox.information(self, title, msg)

    def _confirm(self, title: str, msg: str) -> bool:
        return QMessageBox.question(self, title, msg, QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes

    def persist(self):
        save_data(self.data)

    def refresh_all(self):
        # Summary
        bal = Finance.balance(self.data)
        inc_all = Finance.total_income(self.data)
        exp_all = Finance.total_expenses(self.data)
        inc_m, exp_m = Finance.totals_this_month(self.data)
        net_day = Finance.avg_net_per_day(self.data)
        net_day_txt = "N/A" if net_day is None else f"{fmt_money(net_day)}/day"

        self.lbl_summary.setText(
            f"Balance: {fmt_money(bal)}    |    "
            f"All-time Income: {fmt_money(inc_all)}    |    "
            f"All-time Expenses: {fmt_money(exp_all)}    |    "
            f"This Month: +{fmt_money(inc_m)} / -{fmt_money(exp_m)}    |    "
            f"Avg Net/Day: {net_day_txt}"
        )

        # Refresh each tab’s views
        self._refresh_jobs_view()
        self._refresh_payments_view()
        self._refresh_expenses_view()
        self._refresh_wants_view()

    # --------------------------- Jobs Tab ---------------------------

    def _build_jobs_tab(self):
        lay = QVBoxLayout(self.tab_jobs)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(12)

        # Add job card
        card = Card("Jobs", "Add your jobs (Warehouse OP, Coding, etc.)")
        row = QHBoxLayout()
        self.in_job_name = QLineEdit()
        self.in_job_name.setPlaceholderText("Job name (e.g. Warehouse OP)")
        self.btn_add_job = QPushButton("Add Job")
        self.btn_add_job.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
        self.btn_add_job.clicked.connect(self.add_job)

        row.addWidget(self.in_job_name)
        row.addWidget(self.btn_add_job)
        card.body.addLayout(row)
        lay.addWidget(card)

        # Table
        self.jobs_table = QTableWidget(0, 3)
        self.jobs_table.setHorizontalHeaderLabels(["Name", "Active", "Delete"])
        self.jobs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.jobs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.jobs_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.jobs_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.jobs_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.jobs_table.setSelectionMode(QAbstractItemView.SingleSelection)
        lay.addWidget(self.jobs_table)

    def _refresh_jobs_view(self):
        jobs = self.data["jobs"]
        self.jobs_table.setRowCount(len(jobs))
        for r, job in enumerate(jobs):
            name = QTableWidgetItem(job.get("name", ""))
            name.setFlags(name.flags() ^ Qt.ItemIsEditable)
            self.jobs_table.setItem(r, 0, name)

            chk = QCheckBox()
            chk.setChecked(bool(job.get("active", True)))
            chk.stateChanged.connect(lambda state, jid=job.get("id"): self.toggle_job_active(jid, state))
            self.jobs_table.setCellWidget(r, 1, chk)

            btn = QPushButton("Delete")
            btn.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
            btn.clicked.connect(lambda _, jid=job.get("id"): self.delete_job(jid))
            self.jobs_table.setCellWidget(r, 2, btn)

        self._refresh_jobs_combo()

    def _refresh_jobs_combo(self):
        # Update payment job combo to reflect current jobs
        if hasattr(self, "combo_payment_job"):
            current = self.combo_payment_job.currentData()
            self.combo_payment_job.blockSignals(True)
            self.combo_payment_job.clear()
            for j in self.data["jobs"]:
                self.combo_payment_job.addItem(j.get("name", ""), j.get("id"))
            # restore
            if current:
                idx = self.combo_payment_job.findData(current)
                if idx >= 0:
                    self.combo_payment_job.setCurrentIndex(idx)
            self.combo_payment_job.blockSignals(False)

    def add_job(self):
        name = self.in_job_name.text().strip()
        if not name:
            tells = "Enter a job name."
            self._toast("Missing job name", tells)
            return
        self.data["jobs"].append({"id": new_id(), "name": name, "active": True})
        self.in_job_name.clear()
        self.persist()
        self.refresh_all()

    def toggle_job_active(self, job_id: str, state: int):
        for j in self.data["jobs"]:
            if j.get("id") == job_id:
                j["active"] = (state == Qt.Checked)
                break
        self.persist()
        # No need full refresh, but safe:
        self.refresh_all()

    def delete_job(self, job_id: str):
        # Prevent delete if payments exist for that job
        if any(p.get("job_id") == job_id for p in self.data["payments"]):
            self._toast("Cannot delete",
                        "This job has payments recorded.\nDelete those payments first, then delete the job.")
            return
        if not self._confirm("Delete job", "Are you sure you want to delete this job?"):
            return
        self.data["jobs"] = [j for j in self.data["jobs"] if j.get("id") != job_id]
        self.persist()
        self.refresh_all()

    # --------------------------- Payments Tab ---------------------------

    def _build_payments_tab(self):
        lay = QVBoxLayout(self.tab_payments)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(12)

        card = Card("Payments", "Record income by job and date.")
        row = QHBoxLayout()

        self.combo_payment_job = QComboBox()
        self.combo_payment_job.setMinimumWidth(220)

        self.date_payment = QDateEdit()
        self.date_payment.setCalendarPopup(True)
        self.date_payment.setDate(date.today())

        self.in_payment_amount = QLineEdit()
        self.in_payment_amount.setPlaceholderText("Amount (£)")
        self.in_payment_amount.setMaximumWidth(160)

        self.in_payment_note = QLineEdit()
        self.in_payment_note.setPlaceholderText("Note (optional)")

        self.btn_add_payment = QPushButton("Add Payment")
        self.btn_add_payment.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btn_add_payment.clicked.connect(self.add_payment)

        row.addWidget(QLabel("Job:"))
        row.addWidget(self.combo_payment_job)
        row.addWidget(QLabel("Date:"))
        row.addWidget(self.date_payment)
        row.addWidget(self.in_payment_amount)
        row.addWidget(self.in_payment_note)
        row.addWidget(self.btn_add_payment)

        card.body.addLayout(row)
        lay.addWidget(card)

        self.pay_table = QTableWidget(0, 5)
        self.pay_table.setHorizontalHeaderLabels(["Date", "Job", "Amount", "Note", "Delete"])
        self.pay_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.pay_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.pay_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.pay_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.pay_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.pay_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.pay_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.pay_table.setSelectionMode(QAbstractItemView.SingleSelection)
        lay.addWidget(self.pay_table)

    def _refresh_payments_view(self):
        # Display newest first
        payments = sorted(self.data["payments"], key=lambda p: p.get("date", ""), reverse=True)
        job_map = {j.get("id"): j.get("name", "") for j in self.data["jobs"]}

        self.pay_table.setRowCount(len(payments))
        for r, p in enumerate(payments):
            d = p.get("date", "")
            jn = job_map.get(p.get("job_id"), "Unknown")
            amt = float(p.get("amount", 0.0))
            note = p.get("note", "")

            self.pay_table.setItem(r, 0, QTableWidgetItem(d))
            self.pay_table.setItem(r, 1, QTableWidgetItem(jn))
            self.pay_table.setItem(r, 2, QTableWidgetItem(fmt_money(amt)))
            self.pay_table.setItem(r, 3, QTableWidgetItem(note))

            btn = QPushButton("Delete")
            btn.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
            btn.clicked.connect(lambda _, pid=p.get("id"): self.delete_payment(pid))
            self.pay_table.setCellWidget(r, 4, btn)

        self._refresh_jobs_combo()

    def add_payment(self):
        job_id = self.combo_payment_job.currentData()
        if not job_id:
            self._toast("No job selected", "Add a job first, then select it.")
            return

        amt = safe_float(self.in_payment_amount.text())
        if amt is None or amt <= 0:
            self._toast("Invalid amount", "Enter a valid payment amount.")
            return

        d = self.date_payment.date().toPython()
        note = self.in_payment_note.text().strip()

        self.data["payments"].append({
            "id": new_id(),
            "job_id": job_id,
            "date": d.isoformat(),
            "amount": float(amt),
            "note": note
        })

        self.in_payment_amount.clear()
        self.in_payment_note.clear()

        self.persist()
        self.refresh_all()

    def delete_payment(self, payment_id: str):
        if not self._confirm("Delete payment", "Delete this payment entry?"):
            return
        self.data["payments"] = [p for p in self.data["payments"] if p.get("id") != payment_id]
        self.persist()
        self.refresh_all()

    # --------------------------- Expenses Tab ---------------------------

    def _build_expenses_tab(self):
        lay = QVBoxLayout(self.tab_expenses)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(12)

        card = Card("Expenses", "Track spending (fuel, food, parts, etc.)")
        row = QHBoxLayout()

        self.date_expense = QDateEdit()
        self.date_expense.setCalendarPopup(True)
        self.date_expense.setDate(date.today())

        self.in_expense_amount = QLineEdit()
        self.in_expense_amount.setPlaceholderText("Amount (£)")
        self.in_expense_amount.setMaximumWidth(160)

        self.in_expense_category = QLineEdit()
        self.in_expense_category.setPlaceholderText("Category (e.g. Fuel)")
        self.in_expense_category.setMaximumWidth(200)

        self.in_expense_note = QLineEdit()
        self.in_expense_note.setPlaceholderText("Note (optional)")

        self.btn_add_expense = QPushButton("Add Expense")
        self.btn_add_expense.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btn_add_expense.clicked.connect(self.add_expense)

        row.addWidget(QLabel("Date:"))
        row.addWidget(self.date_expense)
        row.addWidget(self.in_expense_amount)
        row.addWidget(self.in_expense_category)
        row.addWidget(self.in_expense_note)
        row.addWidget(self.btn_add_expense)

        card.body.addLayout(row)
        lay.addWidget(card)

        self.exp_table = QTableWidget(0, 5)
        self.exp_table.setHorizontalHeaderLabels(["Date", "Amount", "Category", "Note", "Delete"])
        self.exp_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.exp_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.exp_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.exp_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.exp_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.exp_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.exp_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.exp_table.setSelectionMode(QAbstractItemView.SingleSelection)
        lay.addWidget(self.exp_table)

    def _refresh_expenses_view(self):
        expenses = sorted(self.data["expenses"], key=lambda e: e.get("date", ""), reverse=True)
        self.exp_table.setRowCount(len(expenses))

        for r, e in enumerate(expenses):
            d = e.get("date", "")
            amt = float(e.get("amount", 0.0))
            cat = e.get("category", "")
            note = e.get("note", "")

            self.exp_table.setItem(r, 0, QTableWidgetItem(d))
            self.exp_table.setItem(r, 1, QTableWidgetItem(fmt_money(amt)))
            self.exp_table.setItem(r, 2, QTableWidgetItem(cat))
            self.exp_table.setItem(r, 3, QTableWidgetItem(note))

            btn = QPushButton("Delete")
            btn.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
            btn.clicked.connect(lambda _, eid=e.get("id"): self.delete_expense(eid))
            self.exp_table.setCellWidget(r, 4, btn)

    def add_expense(self):
        amt = safe_float(self.in_expense_amount.text())
        if amt is None or amt <= 0:
            self._toast("Invalid amount", "Enter a valid expense amount.")
            return

        d = self.date_expense.date().toPython()
        cat = self.in_expense_category.text().strip() or "General"
        note = self.in_expense_note.text().strip()

        self.data["expenses"].append({
            "id": new_id(),
            "date": d.isoformat(),
            "amount": float(amt),
            "category": cat,
            "note": note
        })

        self.in_expense_amount.clear()
        self.in_expense_category.clear()
        self.in_expense_note.clear()

        self.persist()
        self.refresh_all()

    def delete_expense(self, expense_id: str):
        if not self._confirm("Delete expense", "Delete this expense entry?"):
            return
        self.data["expenses"] = [e for e in self.data["expenses"] if e.get("id") != expense_id]
        self.persist()
        self.refresh_all()

    # --------------------------- Wants Tab ---------------------------

    def _build_wants_tab(self):
        lay = QVBoxLayout(self.tab_wants)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(12)

        # Add want card
        card = Card("Wants", "Track goals: progress, £ away, and days away.")
        row = QHBoxLayout()

        self.in_want_name = QLineEdit()
        self.in_want_name.setPlaceholderText("Want name (e.g. 2005 CBR600RR)")
        self.in_want_price = QLineEdit()
        self.in_want_price.setPlaceholderText("Price (£)")
        self.in_want_price.setMaximumWidth(160)

        self.btn_add_want = QPushButton("Add Want")
        self.btn_add_want.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btn_add_want.clicked.connect(self.add_want)

        row.addWidget(self.in_want_name)
        row.addWidget(self.in_want_price)
        row.addWidget(self.btn_add_want)

        card.body.addLayout(row)
        lay.addWidget(card)

        # Scroll area for want cards
        self.wants_scroll = QScrollArea()
        self.wants_scroll.setWidgetResizable(True)
        self.wants_scroll.setFrameShape(QFrame.NoFrame)

        self.wants_container = QWidget()
        self.wants_layout = QVBoxLayout(self.wants_container)
        self.wants_layout.setContentsMargins(0, 0, 0, 0)
        self.wants_layout.setSpacing(12)
        self.wants_layout.addItem(QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.wants_scroll.setWidget(self.wants_container)
        lay.addWidget(self.wants_scroll)

    def _refresh_wants_view(self):
        # Clear old cards (but keep final spacer)
        while self.wants_layout.count() > 1:
            item = self.wants_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

        # Rebuild cards
        wants = self.data["wants"]
        # Sort: unpurchased first, then by remaining ascending
        wants_sorted = sorted(
            wants,
            key=lambda w: (bool(w.get("purchased", False)),
                           Finance.want_remaining(self.data, w))
        )

        for want in wants_sorted:
            card = WantCard(want, on_toggle=self.toggle_purchased, on_delete=self.delete_want)
            card.update_view(self.data)
            self.wants_layout.insertWidget(self.wants_layout.count() - 1, card)

    def add_want(self):
        name = self.in_want_name.text().strip()
        price = safe_float(self.in_want_price.text())

        if not name:
            self._toast("Missing name", "Enter a want name.")
            return
        if price is None or price <= 0:
            self._toast("Invalid price", "Enter a valid price (e.g. 1620).")
            return

        self.data["wants"].append({
            "id": new_id(),
            "name": name,
            "price": float(price),
            "purchased": False
        })

        self.in_want_name.clear()
        self.in_want_price.clear()

        self.persist()
        self.refresh_all()

    def delete_want(self, want: Dict[str, Any]):
        if not self._confirm("Delete want", f"Delete '{want.get('name', '')}'?"):
            return
        wid = want.get("id")
        self.data["wants"] = [w for w in self.data["wants"] if w.get("id") != wid]
        self.persist()
        self.refresh_all()

    def toggle_purchased(self, want: Dict[str, Any]):
        want["purchased"] = not bool(want.get("purchased", False))
        self.persist()
        self.refresh_all()


# --------------------------- Entry ---------------------------

def ensure_seed_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Optional: seed example jobs for first run
    """
    if not data["jobs"]:
        data["jobs"] = [
            {"id": new_id(), "name": "Warehouse OP", "active": True},
            {"id": new_id(), "name": "Coding", "active": True},
        ]
        save_data(data)
    return data


if __name__ == "__main__":
    app = QApplication([])
    apply_dark_theme(app)

    win = MainWindow()
    win.data = ensure_seed_data(win.data)
    win.refresh_all()

    win.show()
    app.exec()
