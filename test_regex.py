import re

ISSUE_REF_RE = re.compile(r"(?i)(?:fix|clos|resolv)(?:e?(?:s|d)?|ing)?\s+#(\d+)")
print(ISSUE_REF_RE.findall("Fixes #101"))
