# IncomeTracker (PySide6)

A modern **desktop income & expense tracker** built with **Python + PySide6 (Qt)**.  
Track jobs, payments, expenses, and saving goals (“wants”) with a clean dark UI, progress bars, and automatic balance calculations.

## Features

### ✅ Jobs
- Add jobs (e.g. *Warehouse OP*, *Coding*)
- Toggle jobs active/inactive
- Prevents deleting a job if payments exist for it (data integrity)

### ✅ Payments (Income)
- Log income by **job + date**
- Optional notes per payment
- Sorted newest-first

### ✅ Expenses
- Track spending with **date + category + amount**
- Optional notes
- Sorted newest-first

### ✅ Goals / Wants
- Add saving goals (“wants”) with a price
- Shows:
  - **£ remaining**
  - **% progress**
  - **estimated days away** (based on average net/day from history)
- Mark wants as purchased
- Smooth progress bar animation

### ✅ Summary Bar (Top)
Displays:
- Current **balance**
- All-time income & expenses
- This month’s income/expenses
- Estimated **average net per day**

## Tech Stack
- **Python 3.10+**
- **PySide6 (Qt Widgets)**
- JSON local storage (`data.json`)

## Data Storage
The app saves data locally to:

- `data.json`

> Tip (recommended for GitHub): don’t commit your real `data.json`.  
Use a `data.sample.json` instead and add `data.json` to `.gitignore`.

## Installation

### 1) Create a virtual environment (recommended)
```bash
python -m venv .venv
