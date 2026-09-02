import re

body = """🎯 **What:** Removed a commented-out example `IYourRepository` interface block from `app/services/data_mesh/domain/ports.py`. Kept the instruction comment `# Add your interfaces here`.
💡 **Why:** Reduces visual clutter and removes unnecessary sample code, thereby improving file readability and maintainability.
✅ **Verification:** Visually verified the file now only contains the module docstring and the `# Add your interfaces here` comment. Confirmed using grep that there are no identical `# Example:` commented protocol blocks in other `app/services/` directories.
✨ **Result:** A cleaner `ports.py` file with unnecessary example code removed, without affecting any application functionality.

---
*PR created automatically by Jules for task [5524077755629049664](https://jules.google.com/task/5524077755629049664) started by @HOUSSAM16ai*"""

print("Done")
