# 🚀 Installation Guide — EMLyzer

Step-by-step instructions for installing EMLyzer on Windows, macOS, and Linux.

> [!IMPORTANT]
> 💻 **Prerequisites:** Review [REQUIREMENTS.md](./REQUIREMENTS.md) before starting.

---

## 📋 Table of Contents

1. [🐍 Install Python 3.13](#1-install-python-313)
   - [🪟 Windows](#windows)
   - [🐧 Linux (Ubuntu/Debian)](#linux-ubuntu--debian)
   - [🍎 macOS](#macos)
2. [⬇️ Download EMLyzer](#2-download-emlyzer)
3. [▶️ First Run](#3-first-run)
4. [✅ Verify Installation](#4-verify-installation)
5. [🔧 Troubleshooting](#5-troubleshoot-common-problems)

---

## 1️⃣ Install Python 3.13

### 🪟 Windows

**Step 1️⃣ — Download Python**

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Click the yellow **"Download Python 3.13.x"** button (latest 3.13.x version)

**Step 2️⃣ — Run the Installer**

1. Double-click the downloaded file (e.g., `python-3.13.2-amd64.exe`)
2. ⚠️ **CRITICAL:** Check the box **"Add Python 3.13 to PATH"** before installing
   - If you skip this, Windows won't find Python later
3. Click **"Install Now"** and wait for completion

**Step 3️⃣ — Verify**

Open Command Prompt (Win key → type `cmd` → Enter):

```cmd
python --version
```

Expected output: `Python 3.13.x` ✅

---

### 🐧 Linux (Ubuntu / Debian)

**Ubuntu 24.04** includes Python 3.12 by default. Install Python 3.13:

```bash
sudo apt update
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.13 python3.13-venv -y
```

Verify:
```bash
python3.13 --version
```

> [!NOTE]
> 💡 Works on Ubuntu 20.04+, Debian 11+, and other Debian-based distros.

---

### 🍎 macOS

**Using Homebrew (Recommended):**

If you don't have Homebrew:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then install Python:
```bash
brew install python@3.13
```

Verify:
```bash
python3.13 --version
```

**Alternative — Download from python.org:**

1. Download `.pkg` from [python.org/downloads/macos](https://www.python.org/downloads/macos/)
2. Run the installer and follow on-screen instructions

---

## 2️⃣ Download EMLyzer

### 📥 Option A: Download ZIP / TAR

1. Go to the GitHub repository
2. Click **"Code"** (green button) → **"Download ZIP"**
3. Extract to a folder:
   - **Windows:** `C:\Users\YourName\EMLyzer\`
   - **Linux/macOS:** `~/EMLyzer/` or `/opt/EMLyzer/`

**If you have .tar.gz:**

**Windows:** Use 7-Zip, WinRAR, or Windows 11 built-in .tar.gz support

**Linux/macOS:**
```bash
tar -xzf EMLyzer_v0.15.1.tar.gz
cd EMLyzer
```

### 🔗 Option B: Clone with Git

If you have Git installed:

```bash
git clone https://github.com/0verwrite/EMLyzer.git
cd EMLyzer
```

---

## 3️⃣ First Run

### 🪟 Windows

1. Open File Explorer
2. Navigate to your `EMLyzer` folder
3. **Double-click `start.bat`**

A black console window opens showing progress:

```
============================================
  EMLyzer v0.15.1
============================================

[INFO] Python found:
Python 3.13.2

[INFO] Creating virtual environment...
[INFO] Virtual environment created.

[INFO] Installing dependencies (first run: a few minutes)...
[INFO] Dependencies OK.

============================================
  Application Ready
============================================

  Open browser:        http://localhost:8000
  API documentation:   http://localhost:8000/docs
  Language:            IT/EN button (top right)

  Press CTRL+C to stop
============================================
```

> ⏱️ **First run takes 2-5 minutes** (downloading Python packages). Subsequent runs start in seconds.

### 🐧 Linux / macOS

Open Terminal in the project folder:

```bash
chmod +x start.sh   # Make executable (first time only)
./start.sh
```

Same output as Windows above.

---

## 4️⃣ Verify Installation

### 🌐 Open the Web Interface

After the console shows "Application Ready", open your browser:

**http://localhost:8000**

You should see:
- ✅ Email upload area
- ✅ Recent analyses list
- ✅ Campaign detection panel
- ✅ IT/EN language selector (top right)

### 🔍 Test the API

Open this link in your browser to verify the backend:

**http://localhost:8000/api/health**

Expected response:
```json
{"status": "ok", "version": "0.15.1", "app": "EMLyzer"}
```

---

## 5️⃣ Troubleshoot Common Problems

### ❌ "Python not found" (Windows)

**Cause:** Python installed but "Add to PATH" wasn't checked

**Solution:**
1. Run Python installer again
2. Click **"Modify"** (or uninstall and reinstall)
3. ✅ Check **"Add Python 3.13 to PATH"**
4. Click **"Install Now"**

**Alternative — Add to PATH manually:**
1. Search "Edit environment variables" in Start menu
2. Go to System variables → **"Path"**
3. Add: `C:\Users\YourName\AppData\Local\Programs\Python\Python313\`
4. Restart Command Prompt

---

### ❌ Dependency Installation Failed (lxml or scikit-learn error)

**Cause:** Using Python 3.14+ or missing C compiler

**Solution:** Use Python 3.13 as described above

If you have multiple Python versions installed, the script auto-selects the correct one. If issues persist:

**Windows:**
```cmd
rmdir /s /q .venv
start.bat
```

**Linux/macOS:**
```bash
rm -rf .venv
./start.sh
```

---

### ❌ "Port 8000 already in use"

**Cause:** Another program uses port 8000 or EMLyzer is running twice

**Solution:**

**Windows:**
```cmd
netstat -ano | findstr :8000
taskkill /PID [number_from_above] /F
start.bat
```

**Linux/macOS:**
```bash
lsof -i :8000
kill [process_id]
./start.sh
```

---

### ❌ Console window closes immediately (Windows)

**Cause:** Error during startup before you can read it

**Solution:**
1. Open Command Prompt manually
2. Navigate to project: `cd C:\Users\YourName\EMLyzer`
3. Run: `start.bat`
4. Now the window stays open and you can see the error

---

### ❌ "Cannot reach the server" (browser)

**Cause:** Server hasn't started or crashed

**Solution:**
1. Check console window is still open and showing "Application Ready"
2. Wait a few seconds and refresh browser (F5)
3. Verify correct URL: **http://localhost:8000** (not https, not port 80)

---

### ❌ "Permission denied" (Linux/macOS)

**Cause:** Script lacks execute permission

**Solution:**
```bash
chmod +x start.sh run_tests.sh
./start.sh
```

---

## 🛑 Stopping the Application

In the console window where the app is running:

**Press `CTRL + C`**

The window shows `[INFO] Server stopped.` and closes (Windows asks for confirmation).

---

## 🔄 Updating EMLyzer

To upgrade to a newer version:

1. Download the new version
2. Extract to the **same folder**, overwriting files (database is preserved)
3. **Delete the virtual environment** to force reinstalling dependencies:

   **Windows:** `rmdir /s /q .venv`
   
   **Linux:** `rm -rf .venv`

4. Run `start.bat` / `start.sh` as usual

> [!WARNING]
> ⚠️ Don't overwrite `backend/.env` if you configured API keys — it contains your settings.

---

## ✅ What's Next?

- **First time?** → Learn the basics in [USAGE.md](./USAGE.md)
- **Need API keys?** → [CONFIGURATION.md](./CONFIGURATION.md)
- **Developer?** → [API.md](./API.md)

---

*← [Requirements](./REQUIREMENTS.md) | Next: [Usage →](./USAGE.md)*
