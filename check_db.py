with open("app/services/system/database_service.py", "r") as f:
    content = f.read()

# Let's restore the original `_is_safe_sqlglot_query` implementation first,
# then fix it properly. The problem is I used a `# noqa` which wasn't enough or caused other issues.

print(content.split("def _is_safe_sqlglot_query")[1][:1000])
