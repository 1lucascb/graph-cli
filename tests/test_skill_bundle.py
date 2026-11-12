import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILL = ROOT / "docs" / "skills" / "graph-lcb"
BUNDLED_SKILL = ROOT / "graph_lcb" / "skills" / "graph-lcb"


def skill_file_hashes(directory: Path) -> dict[str, str]:
    """Return SHA-256 hashes keyed by each file's path within the skill."""
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.rglob("*")
        if path.is_file()
    }


class SkillBundleTests(unittest.TestCase):
    def test_bundled_skill_matches_docs_source(self) -> None:
        self.assertEqual(
            skill_file_hashes(SOURCE_SKILL),
            skill_file_hashes(BUNDLED_SKILL),
            "bundled skill files must match docs/skills/graph-lcb; sync the bundle after editing the source",
        )


if __name__ == "__main__":
    unittest.main()
