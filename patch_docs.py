import re

with open("CLAUDE.md", "r", encoding="utf-8") as f:
    claude_content = f.read()

# Insert core pedagogical engine rules under "Guiding Principles" or Core Invariants
if "## 1. Core Invariants (Doctrines)" in claude_content:
    new_invariant = """
- **Platform is a Pedagogical Engine, NOT an Answer Engine**: Long exercises or educational questions must trigger the pedagogical tutoring flow. The platform must first diagnose the initial cognitive gap, ask one short diagnostic question, and provide only the next missing hint. It must **never** default to dumping the full solution.
- **Strict Intent Routing Safeguards**: Analytical or educational inputs must strictly route to the `educational` pipeline (which engages the Socratic Tutor / Synthesizer). They must **never** fall back to `general_knowledge`.
"""
    claude_content = claude_content.replace("## 1. Core Invariants (Doctrines)\n", f"## 1. Core Invariants (Doctrines)\n{new_invariant}")

with open("CLAUDE.md", "w", encoding="utf-8") as f:
    f.write(claude_content)


with open(".memory/routing_philosophy.md", "r", encoding="utf-8") as f:
    routing_content = f.read()

new_routing_rule = """
## 5. Student Interaction Contract
When a student pastes a long problem description or an analytical question containing words like "تمرين", the system MUST NOT blindly serve a retrieved document or fall back to an answer-machine response (e.g., `general_knowledge`). Instead, it must fall back to the `educational` intent and trigger the tutor (`SynthesizerNode`) to read, analyze, and assist the student pedagogically step-by-step.
"""
routing_content = re.sub(r"## 5\. Student Interaction Contract.*?(?=## 6\.)", new_routing_rule, routing_content, flags=re.DOTALL)

with open(".memory/routing_philosophy.md", "w", encoding="utf-8") as f:
    f.write(routing_content)

print("Documentation updated successfully.")
