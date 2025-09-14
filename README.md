# SVN Auto Commit (Today Only)

A lightweight **PyQt5 tray app** for Windows that watches a chosen folder (even an entire drive), discovers all **SVN working copies** inside it, and **commits only the files changed *today***. It also provides a one-click **Update** action. The window docks in the **bottom-right**, minimizes to **System Tray**, and includes a clean, soft **Material-style** look.

> Built for teams that want automated, *minimal* commits—no more committing a whole working copy when only a few files changed today.

## ✨ Features
- ✅ **Commit only today's changes** (A/M/D) per working copy
- 🔍 **Recursive discovery** of all SVN working-copy roots under any folder/drive
- ⏱️ **Debounced auto-commit** on file changes
- 🔄 **Update Now** button (full update across all working copies)
- 🧰 Works with either **svn.exe** (silent) or **TortoiseSVN TortoiseProc.exe**
- 🪟 **System Tray** friendly; close-to-tray; Exit to quit
- 🎨 Soft, Material-ish UI with mellow colors and system icons
- 🪟 Windows-first (other OSes untested)

---

## 🖥️ Screenshot (placeholder)
*(Add your real screenshot here)*

```
[ Window ]   Folder: C:\projects\ (Browse)
[ Start ] [ Stop ] [ Update Now ] [ Exit ]

Settings:
  Debounce: 5000 ms
  Scan Interval: 2000 ms
  Commit Prefix: Auto-commit (Today)
  Prefer svn.exe: [x]
  Auto update before commit: [x]
  svn.exe: C:\Program Files\TortoiseSVN\bin\svn.exe
  TortoiseProc.exe: C:\Program Files\TortoiseSVN\bin\TortoiseProc.exe

Activity Log:
  ...
```

---

## 🚀 Quick Start

### Prerequisites
- **Windows** (tested) with:
  - [TortoiseSVN](https://tortoisesvn.net/) (for `TortoiseProc.exe`) **and/or**
  - `svn.exe` on PATH (from TortoiseSVN / Subversion / SlikSVN)
- **Python 3.8+**
- `pip install -r requirements.txt`

### Run
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/svn_today_commit.py
```

### Build a Windows EXE (optional)
> *One-file builds may take longer to start; one-folder builds are faster.*
```bash
pip install pyinstaller
# One-folder (recommended during dev)
pyinstaller --noconfirm --windowed --name "SVN Auto Commit Today" src/svn_today_commit.py
# or One-file
pyinstaller --noconfirm --windowed --onefile --name "SVN Auto Commit Today" src/svn_today_commit.py
```
The executable will be in `dist/`.

---

## ⚙️ How it works
- You select any **root folder** (even `D:\`).
- The app **recursively scans** for directories that contain a `.svn` folder (these are working-copy roots).
- It watches the whole tree; when files change it **records only those with mtime ≥ today 00:00** (local time) and schedules a commit **only for those paths** (including deletions detected today).
- Commits happen **per working copy** and can be chunked to avoid command-line length limits.
- **Update** runs full update across all found working copies.

**Adds/Deletes**: If `svn.exe` is available, the app runs `svn add --force` for new files and `svn rm --force` for deleted ones *restricting to today's paths* before committing.

---

## 🧭 Options in Settings
- **Debounce**: time (ms) to wait after last detected change before committing.
- **Scan Interval**: file-system polling period (ms). Increase for very large trees.
- **Commit Prefix**: text prepended to commit messages.
- **Prefer svn.exe**: use CLI for silent commits; otherwise uses `TortoiseProc.exe`.
- **Auto update before commit**: run `svn update` before each auto-commit.
- **svn.exe / TortoiseProc.exe**: explicit paths if not on PATH / auto-detected.

---

## 🛠️ Troubleshooting
- **Nothing commits**: ensure your selected folder actually contains `.svn` working copies; check log for “Found N working copy root(s).”
- **TortoiseProc opens but shows more files**: without `svn.exe`, Tortoise may surface additional changes; configure `svn.exe` path so the app can pre-stage only today's items.
- **Huge folder/drive**: raise **Scan Interval** to reduce CPU/IO; default is 2000 ms.
- **Permissions**: run Python with rights to read/commit in the target folders.

---

## 📦 Project Layout
```
.
├─ src/
│  └─ svn_today_commit.py       # the application
├─ .github/workflows/ci.yml     # lint on each push/PR; build on tags
├─ requirements.txt
├─ .gitignore
├─ LICENSE
└─ README.md
```

---

## 🤝 Contributing
PRs are welcome! Please keep the UI simple and Windows-friendly.
- Run the linter locally:
  ```bash
  pip install ruff
  ruff check .
  ```

---

## 📝 License
MIT — see [LICENSE](LICENSE).

---

## 🇮🇷 راه‌اندازی سریع (فارسی)
1) پایتون ۳.۸ به بالا و TortoiseSVN/‏svn.exe را نصب کنید.  
2) داخل پوشه‌ی پروژه:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/svn_today_commit.py
```
۳) یک فولدر (یا حتی یک درایو) انتخاب کنید. برنامه فقط **فایل‌هایی که امروز تغییر کرده‌اند** را کامیت می‌کند.
