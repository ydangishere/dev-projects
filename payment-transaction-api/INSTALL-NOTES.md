# Docker Installation Complete ✅

## What was installed:
- Docker Desktop 4.60.1 (625MB download)
- Installed to: `C:\Program Files\Docker\`
- Current data location: `C:\Users\Admin\AppData\Local\Docker\` (~2-3GB)

---

## 🔄 NEXT STEPS:

### 1. Install WSL (REQUIRED for Docker)

**Right-click** `install-wsl.ps1` → **Run as Administrator**

Or manually:
```powershell
# In PowerShell (as Admin):
wsl --install
```

This will:
- Enable WSL feature
- Download Ubuntu (~500MB)
- Install WSL 2 kernel
- Takes 5-10 minutes

### 2. Restart Your Computer (REQUIRED)
```
Restart-Computer
```
Docker needs a restart to enable WSL 2 backend.

---

### 2. After Restart: Move Docker Data to D:\

**Option A: Automatic Script**
```powershell
cd d:\order-concurrency-lab
.\move-docker-to-d.ps1
```
Script will guide you through the manual steps.

**Option B: Manual Steps**
1. Open Docker Desktop
2. Click ⚙️ Settings (top right)
3. Go to: **Resources → Advanced**
4. Find **"Disk image location"**
5. Change to: `D:\DockerData`
6. Click **"Apply & Restart"**

Docker will automatically move ~2-3GB data from C:\ to D:\

---

### 3. Verify Installation

After Docker restarts:

```powershell
# Check Docker version
docker --version

# Check Docker Compose
docker compose version

# Test with hello-world
docker run hello-world
```

Expected output: "Hello from Docker!"

---

### 4. Run Your Payment API Project

```powershell
cd d:\order-concurrency-lab
docker compose up --build
```

API will be available at: http://localhost:8000

---

## 📊 Disk Space After Move:

| Location | Before | After Move to D:\ |
|----------|--------|-------------------|
| **C:\ (Program Files)** | 500MB | 500MB (no change) |
| **C:\ (AppData/Docker data)** | 2-3GB | 0MB ✅ |
| **D:\ (DockerData)** | 0MB | 2-3GB ✅ |
| **Total C:\ saved** | - | ~2-3GB |

---

## 🔧 Troubleshooting

### Docker Desktop won't start after restart
- Wait 1-2 minutes (first startup is slow)
- Check if WSL 2 is enabled: `wsl --status`
- If needed: `wsl --install`

### Can't find Settings in Docker Desktop
- Make sure Docker Desktop app is running (system tray icon)
- Click the Docker whale icon → Dashboard → Settings

### Data not moving
- Make sure you clicked "Apply & Restart" after changing path
- Check D:\ has enough space (~3GB free)
- Docker will show progress bar while moving

---

## ✅ Installation Summary

- **Installed**: Docker Desktop 4.60.1
- **Location**: C:\Program Files\Docker\
- **Status**: ⚠️ Restart required
- **Next**: Restart → Move data to D:\ → Run project

---

**Questions?** Check README.md or QUICKSTART.md for full documentation.
