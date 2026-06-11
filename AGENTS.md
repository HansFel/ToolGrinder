# ToolGrinder Agent Guide

This repository generates machine-moving G-code. Treat every change to motion,
probing, coordinate systems, feeds, limits, or result calculations as
safety-critical.

## Shared Goal

Build a reliable four-axis CNC tool-grinding generator for X/Y/Z/A machines,
including LinuxCNC probing. Generated G-code must be understandable, bounded by
configured machine limits, and covered by focused tests before it is considered
ready for a machine trial.

## Source Of Truth

- `Grinder.py`: G-code generation, validation, probing, and desktop CLI/GUI.
- `webapp.py`: Flask API and web generation workflow.
- `ToolLib/*.json`: machine and tool configuration examples.
- `tests/`: executable behavior contract.
- `README.md`: operator-facing description of current behavior.
- Generated `.ngc` files are artifacts, not implementation sources.

Read the relevant generator, its tests, and the active JSON template before
changing behavior. Do not infer machine geometry from field names alone.

## Agent Roles

### Codex: Coordinator And Integrator

- Owns task decomposition, repository inspection, implementation, and final
  verification.
- Keeps changes scoped and resolves conflicting suggestions.
- Runs the complete Python test suite and reviews generated G-code.
- Is the only agent that should commit, push, or open pull requests unless the
  user explicitly delegates that action.

### Claude Code In WSL: Independent Safety Reviewer

- Best used for LinuxCNC semantics, probing state machines, geometry, and
  review of non-obvious changes.
- Default invocation from Windows:

  ```powershell
  wsl.exe -d Ubuntu-24.04 -- bash -lc \
    'cd /mnt/c/Users/HTFel/OneDrive/CNCProgramms/Grinder && claude -p "<task>"'
  ```

- Review prompts should request findings only, ordered by severity, with
  file/line references and a proposed test for every behavioral concern.
- Claude must not edit files during a review task. Give it an explicitly
  isolated implementation task only when no other agent is editing those files.

### Mistral: Focused Second Opinion

- Best used for small, bounded tasks: checking formulas, finding missing edge
  cases, proposing test matrices, or reviewing a single diff.
- Provide the exact files or diff, assumptions, and desired output format.
- Ask for concise findings, not a competing rewrite.
- The local Mistral launcher is environment-specific. Record its working
  command here when confirmed; until then, invoke it through the user's
  configured Mistral interface.

## Coordination Protocol

1. Codex writes a short task statement with acceptance criteria.
2. Only one agent edits a given file at a time.
3. Review agents return findings; they do not silently modify the worktree.
4. Every handoff includes:
   - files inspected or changed
   - assumptions about machine coordinates and LinuxCNC
   - commands run and their results
   - unresolved risks
5. Codex integrates accepted findings and reruns the full verification.

Use this review request format:

```text
Task:
Scope:
Machine assumptions:
Acceptance criteria:
Files/diff:
Return: findings ordered by severity, then missing tests. Do not edit files.
```

## Engineering Rules

- Preserve existing configuration compatibility unless a migration is
  explicitly requested.
- Validate numeric inputs before generating motion.
- Use unique LinuxCNC O-word labels. Never reuse a label for different blocks.
- Guard runtime probe failures and account for preview mode with `#<_task>`.
- Keep rapid moves at a configured safe clearance before rotating A or moving X/Y.
- Run generated numeric axis words through machine-limit validation.
- Persistent LinuxCNC result parameters must be configurable, unique integers in
  the user range `31..5000`.
- Avoid broad refactors of `Grinder.py`; it is large and carries legacy GUI code.
- Do not commit local secrets, SSH keys, generated G-code, caches, or OneDrive
  state files.

## Verification

From the repository root:

```powershell
python -m unittest discover -s tests -v
python -m py_compile Grinder.py webapp.py
git diff --check
```

For probing changes, also generate a measurement program and inspect it for:

- safe Z before X/Y/A positioning
- a guarded probe move for every contact attempt
- unique and matched O-word blocks
- correct probe-ball compensation
- one-flute-pitch A search
- normalized angular difference for helix calculation
- persistent result assignments and readable operator output
- final safe retract and `M30`

Passing unit tests does not authorize unattended machine execution. The first
run of changed motion must use LinuxCNC simulation or a dry run with feed
override reduced and enough clearance to stop safely.
