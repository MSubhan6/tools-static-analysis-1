# Companion Server Setup Guide

## What is the Companion Server?

The **companion server** is a lightweight Node.js service that enables the MCP server and viewer to launch local editors (Claude Code, VS Code, GitHub Copilot) from the browser.

It runs on `localhost:19280` (default) and handles:
- Editor launches (Claude Code, OpenCode, VS Code)
- Fix workflow orchestration (branch → fix → test → submit)
- Version control integration (Git, SVN)

## Windows Installation

### Quick Download (Windows 10/11)

1. **Download the companion server:**
   - Open: http://localhost:8080/companion/download
   - Saves as: `companion-server.zip`

2. **Extract the ZIP file:**
   - Right-click `companion-server.zip`
   - Select "Extract All..."
   - Choose destination (e.g., `C:\companion`)

3. **Start the server:**
   ```cmd
   cd C:\companion\companion
   node server.js
   ```

   Or:
   ```cmd
   cd C:\companion\companion
   npm start
   ```

4. **Verify it's running:**
   ```cmd
   curl http://localhost:19280/_ping
   ```

   Expected response: `{"status":"ok"}`

### Requirements (Windows)

- Node.js v16+ (Download from: https://nodejs.org)
- Windows 10 or later
- No additional tools needed (ZIP extraction is built-in)

### Default Settings

- **Port:** 19280 (configurable with `--port` flag)
- **Config:** Optional `config.yaml` in project root
- **Auto-start:** No - manual start required

### Troubleshooting (Windows)

**Port 19280 already in use:**
```cmd
node server.js --port 19281
```

**Can't find node command:**
- Install Node.js from https://nodejs.org
- Restart your terminal after installation

## Quick Start (Unix/Linux/Mac)

### 1. Install Node.js (if needed)

**Check if installed:**
```bash
node --version
# Should show v16+ (v18+ recommended)
```

**Install if needed:**
```bash
# Ubuntu/Debian
sudo apt install nodejs npm

# macOS
brew install node

# Or download from: https://nodejs.org
```

### 2. Start the Companion Server

**Option A: Default settings (port 19280)**
```bash
cd dependency-mapper-python
node companion/server.js
```

**Option B: Custom port**
```bash
node companion/server.js --port 19281
```

**Option C: With config file**
```bash
node companion/server.js --config /path/to/config.yaml
```

### 3. Verify it's Running

**In another terminal:**
```bash
curl http://localhost:19280/_ping
# Should return: {"status":"ok","version":"1.0.0"}
```

**Or open in browser:**
```
http://localhost:19280/_ping
```

---

## Full Setup Instructions

### Step 1: Navigate to Project Directory

```bash
cd /home/user/dependency-mapper-python
```

### Step 2: Check Dependencies

The companion server uses **only Node.js built-ins** (no `npm install` needed!).

Required:
- Node.js v16+ (v18+ recommended)
- `companion/server.js` (already in repo)
- `companion/fix-workflow.js` (already in repo)

### Step 3: Create/Configure config.yaml (Optional)

The companion server can use a `config.yaml` in the project root:

```yaml
# config.yaml (optional - has sensible defaults)

# Claude Code settings
claudeCodePath: "claude"                    # Or full path: /usr/local/bin/claude
claudePrompt: "Analyze this code and propose improvements."

# GitHub Copilot settings
githubCopilotEnabled: true
copilotMode: "standalone"                   # or "chat"
copilotCliPath: "copilot"
copilotModel: "claude-opus-4.6"

# Fix workflow settings (for start_fix_with_context)
vcsType: "git"                              # or "svn"
repoUrl: ""                                 # Auto-detected from .git
svnBranchBase: ""                           # For SVN only
developerRoot: ""                           # Optional working directory
fixBranchPrefix: "fix/smell-"              # Branch name prefix
prTargetBranch: "main"
testCommand: "pytest tests/"                # Or "npm test", "mvn test"
autoRunTests: true
buildCommand: "npm run build"               # Or "mvn package"
testTimeoutSec: 300
```

**Default config** (if no config.yaml exists):
- Port: 3000
- Claude Code path: `claude` (from PATH)
- Copilot enabled: true
- VCS: SVN (auto-detects .git)
- Test timeout: 300 seconds

### Step 4: Start the Server

**Terminal 1 (Companion Server):**
```bash
node companion/server.js
```

**Expected output:**
```
Companion agent started on port 19280
   Endpoints:
     GET http://localhost:19280/_ping
     GET http://localhost:19280/_open?editor=claude&path=...
     GET http://localhost:19280/_fix/start?smell_type=...
     GET http://localhost:19280/_fix/status?fix_id=...

   Ready to launch editors
```

**Terminal 2 (Your work):**
```bash
# Now you can use the MCP server or run scans
python run.py --repos eShop --out output-eshop

# Or start the MCP server
python -m static_analysis_mcp.server
```

---

## Port Configuration

### Default Port: 3000

The companion server uses port **3000** by default.

**Change port:**
```bash
# Command line
node companion/server.js --port 19280

# Or in config.yaml
companionPort: 19280
```

### MCP Server Configuration

The MCP server connects to the companion server on the configured port.

**In `static_analysis_mcp/config.py`:**
```python
companion_port: int = 3000  # Must match companion server port
```

**Or set environment variable:**
```bash
export COMPANION_PORT=19280
python -m static_analysis_mcp.server
```

---

## Running as a Background Service

### Option 1: Using `nohup`

```bash
nohup node companion/server.js > companion.log 2>&1 &
echo $! > companion.pid
```

**Check status:**
```bash
curl http://localhost:19280/_ping
```

**Stop:**
```bash
kill $(cat companion.pid)
```

### Option 2: Using `systemd` (Linux)

Create `/etc/systemd/system/companion.service`:

```ini
[Unit]
Description=Static Analysis Companion Server
After=network.target

[Service]
Type=simple
User=user
WorkingDirectory=/home/user/dependency-mapper-python
ExecStart=/usr/bin/node companion/server.js
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl enable companion
sudo systemctl start companion
sudo systemctl status companion
```

### Option 3: Using `pm2` (Recommended for Development)

```bash
# Install pm2 globally
npm install -g pm2

# Start companion
pm2 start companion/server.js --name companion

# View logs
pm2 logs companion

# Stop
pm2 stop companion

# Restart
pm2 restart companion

# Auto-start on boot
pm2 startup
pm2 save
```

---

## Troubleshooting

### Issue 1: "Port 3000 already in use"

**Cause:** Another service is using port 19280.

**Solution A:** Use a different port
```bash
node companion/server.js --port 19280
```

**Solution B:** Find and stop the conflicting service
```bash
# Linux/Mac
lsof -i :3000
kill <PID>

# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F
```

### Issue 2: "Cannot find module './fix-workflow'"

**Cause:** Running from wrong directory.

**Solution:** Always run from project root
```bash
cd /home/user/dependency-mapper-python
node companion/server.js
```

### Issue 3: "Failed to connect to companion agent on port 19280"

**Cause:** Companion server not running when MCP server tries to connect.

**Solution:** Start companion first, then MCP
```bash
# Terminal 1
node companion/server.js

# Terminal 2 (after companion is running)
python -m static_analysis_mcp.server
```

### Issue 4: "EACCES: permission denied"

**Cause:** Port below 1024 requires root (or port already in use).

**Solution:** Use port 19280+ or run with sudo (not recommended)
```bash
node companion/server.js --port 19280
```

### Issue 5: "claude: command not found"

**Cause:** Claude Code not in PATH.

**Solution A:** Install Claude Code
- Download from: https://claude.ai/download
- Or: `npm install -g @anthropic-ai/claude-code`

**Solution B:** Configure full path in config.yaml
```yaml
claudeCodePath: "/usr/local/bin/claude"
```

---

## API Endpoints

Once running, the companion server exposes:

### `GET /_ping`
Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "port": 3000
}
```

### `GET /_open`
Launch an editor.

**Parameters:**
- `editor` - Editor to launch (`claude`, `opencode`, `copilot`, `vscode`)
- `path` - File path to open
- `line` - Optional line number

**Example:**
```bash
curl "http://localhost:19280/_open?editor=claude&path=/home/user/test.cs&line=45"
```

### `GET /_fix/start`
Start a fix workflow.

**Parameters:**
- `smell_type` - Type of code smell
- `path` - File path
- `line` - Line number
- `project` - Project name
- `smell` - Smell description
- `editor` - Editor to use (default: claude)

**Returns:**
```json
{
  "fix_id": "sql_injection-UserController-45",
  "status": "fixing",
  "editor": "claude",
  "branch": "fix/sql-injection-usercontroller"
}
```

### `GET /_fix/status`
Check fix workflow status.

**Parameters:**
- `fix_id` - Fix identifier from start

**Returns:**
```json
{
  "fix_id": "sql_injection-UserController-45",
  "status": "testing",
  "progress": {
    "checkout": "done",
    "branch": "done",
    "fix": "done",
    "build": "done",
    "test": "in_progress"
  }
}
```

---

## Integration with MCP Server

The MCP server's fix workflow tools connect to the companion server:

**MCP Tools that use companion:**
- `start_fix` - Basic fix workflow
- `start_fix_with_context` - Enhanced with confidence check
- `get_fix_status` - Check fix progress
- `submit_fix` - Submit PR or patch
- `cancel_fix` - Cancel workflow

**Connection flow:**
```
MCP Server (port 8080 or stdio)
    ↓
    HTTP GET to companion
    ↓
Companion Server (port 19280)
    ↓
    Launches editor (Claude Code, etc.)
    ↓
    Manages VCS workflow (git/svn)
```

---

## Security Notes

### Localhost Only

The companion server **only binds to localhost** (127.0.0.1). It cannot be accessed from other machines.

**This is by design** - it's a local helper, not a web service.

### No Authentication

There is **no authentication** because:
1. Only accessible from localhost
2. Only launches editors you already have installed
3. No sensitive data stored

### Firewall

No firewall rules needed - localhost traffic is not blocked.

---

## Development Mode

### Enable Debug Logging

```bash
# Set environment variable
DEBUG=* node companion/server.js

# Or add logging to server.js
```

### Watch Mode (Auto-restart on changes)

```bash
# Install nodemon
npm install -g nodemon

# Run with auto-restart
nodemon companion/server.js
```

---

## Summary

**Installation:**
```bash
# 1. Check Node.js installed
node --version

# 2. Navigate to project
cd dependency-mapper-python

# 3. Start companion
node companion/server.js
```

**Verification:**
```bash
# In another terminal
curl http://localhost:19280/_ping
# Should return: {"status":"ok"}
```

**Integration:**
```bash
# Now start MCP server (it will connect to companion)
python -m static_analysis_mcp.server
```

**That's it!** The companion server is now ready to handle editor launches and fix workflows.

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│ COMPANION SERVER QUICK REFERENCE                            │
├─────────────────────────────────────────────────────────────┤
│ Start:    node companion/server.js                          │
│ Port:     3000 (default)                                     │
│ Check:    curl http://localhost:19280/_ping                  │
│ Logs:     stdout (or redirect to file)                      │
│ Stop:     Ctrl+C (or kill process)                          │
│                                                              │
│ Config:   config.yaml (optional)                            │
│ No deps:  Uses only Node.js built-ins                       │
│                                                              │
│ Endpoints:                                                   │
│   /_ping              - Health check                         │
│   /_open              - Launch editor                        │
│   /_fix/start         - Start fix workflow                   │
│   /_fix/status        - Check fix status                     │
│   /_fix/submit        - Submit PR/patch                      │
│   /_fix/cancel        - Cancel workflow                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Need Help?

**Common issues:**
- Port in use → Use `--port <number>`
- Can't find companion → Run from project root
- Connection failed → Start companion before MCP server

**Still stuck?** Check the logs or file an issue.
