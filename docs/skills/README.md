# Agent skills

The source of truth for the bundled graph-lcb agent skill is
[`graph-lcb/`](graph-lcb/). Edit its `SKILL.md` and `references/` files when
updating the skill.

The copy under [`../../graph_lcb/skills/graph-lcb/`](../../graph_lcb/skills/graph-lcb/)
is included in the Python package and is the version installed by
`graph install-skill`. Keep it synchronized with the source in this folder.
The `tests/test_skill_bundle.py` test compares SHA-256 hashes for every file in
both directories and fails if a file is missing, extra, or different.
