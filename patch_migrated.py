with open("tests/contract/test_api_contract.py", "r") as f:
    content = f.read()

new_paths = """    "/admin/api/chat/ws",
    "/admin/api/chat/latest",
    "/admin/api/conversations",
    "/admin/api/conversations/{conversation_id}",
    "/admin/users/count",
    "/api/chat/ws",
    "/api/chat/conversations",
    "/api/chat/conversations/{conversation_id}",
    "/api/chat/latest","""

content = content.replace('"/admin/ai-config",', new_paths + '\n    "/admin/ai-config",')

with open("tests/contract/test_api_contract.py", "w") as f:
    f.write(content)
