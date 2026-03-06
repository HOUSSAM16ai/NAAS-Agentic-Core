with open("app/services/chat/orchestrator.py", "r") as f:
    content = f.read()

content = content.replace("from app.services.overmind.identity import OvermindIdentity", "from microservices.orchestrator_service.src.services.overmind.identity import OvermindIdentity")

with open("app/services/chat/orchestrator.py", "w") as f:
    f.write(content)
