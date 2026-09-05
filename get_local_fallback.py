with open("app/infrastructure/clients/orchestrator/turn_fallback.py", "r") as f:
    content = f.read()

start_idx = content.find("local_file_count_response = await self._build_local_file_count_response(")
print(content[start_idx-100:start_idx+100])
