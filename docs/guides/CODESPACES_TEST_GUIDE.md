# 🚀 Quick Start - Testing Codespaces Crash Fix

## دليل الاختبار السريع في Codespaces

This guide will help you verify that the Codespaces crash issue has been fixed.

---

## ✅ Pre-Testing Checklist

Before you begin, ensure:
- [ ] You have access to GitHub Codespaces
- [ ] The PR has been merged or branch is deployed
- [ ] You have admin credentials ready

---

## 📋 Step-by-Step Testing Guide

### Step 1: Create Codespace

1. Go to the repository: https://github.com/Houssam-lab/NAAS-Agentic-Core
2. Click on **Code** → **Codespaces** → **Create codespace on [branch-name]**
3. Wait for the Codespace to initialize (2-3 minutes)

### Troubleshooting: "Workspace does not exist"

If VS Code Web shows **Workspace does not exist**, it usually means the Codespace was stopped, renamed, or deleted while the browser tab stayed open. Use the following recovery steps:

1. Close the current browser tab.
2. Open https://github.com/codespaces and verify the Codespace is **Running**.
3. If it is stopped, click **Start**. If it no longer exists, click **Create codespace** again on the correct branch.
4. Reopen the Codespace from the Codespaces list instead of using the old URL.

**ملاحظة بالعربية:**  
ظهور رسالة **Workspace does not exist** يعني غالباً أن الـ Codespace تم إيقافه أو حذفه بينما التبويب ما زال مفتوحاً. أغلق التبويب، ثم افتح قائمة Codespaces من GitHub وشغّل الـ Codespace أو أنشئ واحداً جديداً على نفس الفرع، وبعدها افتحه من القائمة مباشرة.

### Troubleshooting: Recovery mode بسبب خطأ في الإعدادات

If you see a banner that says the Codespace is running in **recovery mode due to a configuration error**, it means the devcontainer build failed. Fix it by following these steps:

1. Click **View Creation Log** to see the exact dependency error.
2. Apply the dependency pins from this repo (the `constraints.txt` + `requirements.txt` are already aligned).
3. Back in Codespaces, click **Rebuild Container** from the command palette or the Codespaces menu.

**ملاحظة بالعربية:**  
وضع **recovery mode** يظهر عندما يفشل بناء الـ devcontainer. افتح **View Creation Log** لمعرفة الخطأ، ثم أعد البناء عبر **Rebuild Container** بعد تطبيق الإصلاحات.

### Step 2: Wait for Application Startup

The application will start automatically. Monitor the terminal for:

```
🎉 Application Lifecycle Complete - SUPER SMOOTH STARTUP
```

**Expected time**: 2-5 minutes depending on first-time setup

### Step 3: Run Diagnostic Check

Once the application is ready, run the diagnostic script:

```bash
bash scripts/codespaces_diagnostic.sh
```

**Expected output**:
```
╔══════════════════════════════════════════════════════════════════╗
║       GitHub Codespaces Health Diagnostic v1.0.0                ║
╚══════════════════════════════════════════════════════════════════╝

✅ OK - Running in GitHub Codespaces
✅ OK - CPUs: X cores, Load: X.XX
✅ OK - Memory: XXX / XXX used (XX%)
✅ OK - Uvicorn running (PID: XXXX)
✅ OK - Port 8000 is listening
✅ OK - Health endpoint is healthy
✅ OK - Root endpoint is accessible
✅ OK - .env file exists
```

If any checks fail, **DO NOT PROCEED** - review the diagnostic output.

### Step 4: Open the Application

1. In the **PORTS** tab, find port **8000**
2. Click the **🌐 globe icon** to open in browser
3. Or use the URL: `https://[codespace-name]-8000.preview.app.github.dev/`

**CRITICAL**: Ensure port 8000 is set to **Public** visibility

### Step 5: Check Browser Console

Before logging in:

1. Open browser Developer Tools (F12)
2. Go to **Console** tab
3. Look for the startup banner:

```
╔══════════════════════════════════════════════════════════════════╗
║             CogniForge V3 - Startup Diagnostics                 ║
╚══════════════════════════════════════════════════════════════════╝
🌍 Environment: GitHub Codespaces
📊 Performance Limits:
   - MAX_MESSAGES: 10
   - STREAM_UPDATE_THROTTLE: 400ms
   - STREAM_MICRO_DELAY: 12ms
   - MAX_STREAM_CHUNK_SIZE: 800 chars
💾 Memory Limit: XXXX MB
⚙️ React Version: 17.x.x
✅ Application initialized successfully
```

**Verify**:
- ✅ Environment detected as "GitHub Codespaces"
- ✅ Optimized limits are active (MAX_MESSAGES=10, THROTTLE=400ms)

### Step 6: Login Test (CRITICAL)

1. Enter admin credentials:
   - Email: `admin@example.com` (or from your .env)
   - Password: `password` (or from your .env)

2. Click **Login**

**EXPECTED BEHAVIOR**:
- ✅ Login succeeds
- ✅ Dashboard loads
- ✅ **Browser does NOT crash**
- ✅ **Desktop does NOT reload**
- ✅ You remain on the chat interface

**If browser crashes here, the fix did NOT work** ❌

### Step 7: Monitor Memory (5 minutes)

Keep the browser console open and run this command:

```javascript
// Paste in browser console
setInterval(() => {
    if (performance.memory) {
        const used = (performance.memory.usedJSHeapSize / 1024 / 1024).toFixed(1);
        const limit = (performance.memory.jsHeapSizeLimit / 1024 / 1024).toFixed(0);
        const percent = ((performance.memory.usedJSHeapSize / performance.memory.jsHeapSizeLimit) * 100).toFixed(1);
        console.log(`📊 Memory: ${used}MB / ${limit}MB (${percent}%)`);
    }
}, 10000);
```

**Expected output every 10 seconds**:
```
📊 Memory: 45.2MB / 2048MB (2.2%)
📊 Memory: 48.7MB / 2048MB (2.4%)
📊 Memory: 52.1MB / 2048MB (2.5%)
```

**Good signs** ✅:
- Memory usage stays between 40-80MB
- Memory grows slowly and stabilizes
- No warnings about high memory usage

**Bad signs** ❌:
- Memory exceeds 200MB within 5 minutes
- Memory grows continuously without stabilizing
- Console shows memory warnings

### Step 8: Stress Test - Chat Messages (10 minutes)

Send multiple chat messages to test streaming:

1. Send a simple message: "Hello"
2. Wait for response
3. Send a longer message: "Explain how JavaScript closures work in detail"
4. Observe streaming behavior
5. Repeat 5-10 times

**Expected behavior**:
- ✅ Responses stream smoothly
- ✅ No lag or freezing
- ✅ Memory stays under 100MB
- ✅ CPU usage reasonable (check Task Manager)
- ✅ No browser crashes

### Step 9: Conversation Loading Test

1. Click **New Chat** button
2. Send a message
3. Click on another conversation in the sidebar
4. Load previous conversation
5. Repeat 3-4 times

**Expected behavior**:
- ✅ Conversations load without errors
- ✅ Messages display correctly
- ✅ No memory spikes
- ✅ Smooth transitions

### Step 10: Health Monitoring Test (15+ minutes)

Leave the application open for 15 minutes:

1. Send occasional messages (every 2-3 minutes)
2. Keep browser console open
3. Monitor for:
   - Memory warnings
   - Health check failures
   - JavaScript errors
   - Network errors

**Expected console output**:
- Occasional memory snapshots (if enabled)
- No error messages
- No health check failures
- No automatic reloads (unless memory >95%)

---

## 🎯 Success Criteria

The fix is successful if ALL of the following are true:

- ✅ Application starts successfully in Codespaces
- ✅ Diagnostic script shows all green checks
- ✅ Browser console shows Codespaces environment detected
- ✅ Login works without browser crash
- ✅ Memory stays under 100MB for 15+ minutes
- ✅ Chat streaming works smoothly
- ✅ No JavaScript errors in console
- ✅ No automatic reloads occur
- ✅ Application remains stable throughout testing

---

## ❌ Failure Scenarios

If any of these occur, the fix needs more work:

| Symptom | Likely Cause | Action |
|---------|--------------|--------|
| Browser crashes on login | History API issue | Check console for errors |
| Memory exceeds 200MB | Memory leak | Check for runaway timers |
| Continuous memory growth | Resource cleanup issue | Check component unmounting |
| Streaming is choppy | Throttle too aggressive | Adjust STREAM_UPDATE_THROTTLE |
| Health checks fail | Server issue | Run diagnostic script |
| Automatic reload happens | Memory >95% or health failure | Check console for trigger |

---

## 🔍 Debugging Commands

If issues occur, run these commands:

### Check Application Status
```bash
bash scripts/codespaces_diagnostic.sh
```

### Check Process Status
```bash
ps aux | grep uvicorn
```

### Check Memory Usage
```bash
free -h
```

### Check Logs
```bash
tail -f .superhuman_bootstrap.log
```

### Restart Application
```bash
pkill -f uvicorn
bash .devcontainer/supervisor.sh
```

---

## 📊 Test Results Template

Use this template to report results:

```markdown
## Codespaces Crash Fix - Test Results

**Date**: YYYY-MM-DD  
**Tester**: [Your Name]  
**Branch**: [branch-name]  
**Codespace**: [codespace-url]

### Pre-Testing
- [ ] Diagnostic script passed
- [ ] Environment detected as Codespaces
- [ ] Optimized limits active

### Login Test
- [ ] Login successful
- [ ] No browser crash
- [ ] Dashboard loaded

### Memory Test (15 min)
- Peak memory usage: ___ MB
- Average memory usage: ___ MB
- Memory warnings: [ ] Yes [ ] No

### Functionality Test
- [ ] Chat streaming works
- [ ] Conversation loading works
- [ ] New chat creation works
- [ ] Logout works

### Stability Test
- Total test duration: ___ minutes
- Crashes: [ ] Yes [ ] No
- Errors in console: [ ] Yes [ ] No
- Health check failures: [ ] Yes [ ] No

### Overall Result
- [ ] ✅ PASS - All tests successful
- [ ] ❌ FAIL - Issues found (describe below)

**Notes**:
[Add any observations, issues, or comments here]
```

---

## 🆘 Getting Help

If you encounter issues:

1. **Capture diagnostic output**:
   ```bash
   bash scripts/codespaces_diagnostic.sh > diagnostic_output.txt
   ```

2. **Capture browser console**:
   - Right-click in console
   - "Save as..." → save the log

3. **Note the exact steps** to reproduce the issue

4. **Report** with all the above information

---

## 📚 Related Documentation

- `CODESPACES_CRASH_FIX_FINAL.md` - Complete technical documentation
- `scripts/codespaces_diagnostic.sh` - Diagnostic tool
- `tests/test_codespaces_fix.py` - Automated verification tests

---

**Good luck with testing! 🚀**

**حظ موفق في الاختبار!** ✨
