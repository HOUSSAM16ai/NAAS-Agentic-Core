import json
with open('docs/changes/CURRENT_CODE_ACCEPTANCE_PACKET.json', 'r') as f:
    packet = json.load(f)

packet['changed_paths'] = [
    "docs/changes/CURRENT_CODE_ACCEPTANCE_PACKET.json",
    "app/services/data_mesh/domain/ports.py"
]

packet['deletions']['paths'] = []

with open('docs/changes/CURRENT_CODE_ACCEPTANCE_PACKET.json', 'w') as f:
    json.dump(packet, f, indent=2)
