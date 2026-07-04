# Characterization Tests (Gate 3)

## Added Tests

### ProjectKnowledge environment snapshot
- **File:** `tests/unit/test_project_knowledge_environment.py`
- **Why:** `ProjectKnowledge.get_environment_info()` is used by the Overmind knowledge subsystem, which is a high-risk SRP/DIP slice. We added characterization tests to lock behavior for environment flags before refactoring.
- **Behavior Covered:**
  - Default flags when no AI/Supabase/runtime variables are set.
  - Runtime flags when Codespaces/Gitpod/AI/Supabase variables are provided.
