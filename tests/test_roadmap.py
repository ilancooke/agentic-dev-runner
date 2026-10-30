import unittest

from agentic_runner.diagnostics import DiscoveryError
from agentic_runner.roadmap import parse_roadmap
from tests.support.projects import ROADMAP


class RoadmapTests(unittest.TestCase):
    def test_valid_order_and_selection(self):
        result = parse_roadmap(ROADMAP)
        self.assertEqual([m.id for m in result.milestones], ["M1", "M2"])
        self.assertEqual(result.next_milestone, "M2")
        self.assertEqual(result.milestones[1].title, "Feature")
        self.assertEqual(parse_roadmap(ROADMAP.replace("not started", "in progress")).next_milestone, "M2")
        self.assertIsNone(parse_roadmap(ROADMAP.replace("not started", "complete")).next_milestone)

    def test_markdown_bodies_are_preserved_and_fenced_headings_ignored(self):
        body = """Ordinary **Markdown** with [requirements](docs/spec.md#details).

| Example | Value |
| --- | --- |
| Input | `1` |

#### Details

~~~markdown
## M99 — A fenced example
### Deliverables
### Acceptance criteria
~~~
""".strip()
        result = parse_roadmap(ROADMAP.replace("Implement the feature.", body))
        self.assertEqual(result.milestones[1].deliverables, body)

    def test_invalid_roadmaps_never_select(self):
        invalid = {
            "missing progress": ROADMAP.replace("## Milestone Progress", "## Progress"),
            "duplicate progress": ROADMAP + "\n## Milestone Progress\n",
            "bad header": ROADMAP.replace("| Milestone | Status |", "| Item | Status |"),
            "bad separator": ROADMAP.replace("| --- | --- |", "| - | - |"),
            "malformed ID": ROADMAP.replace("| M2 |", "| M02 |"),
            "nonnumeric ID": ROADMAP.replace("| M2 |", "| MX |"),
            "duplicate row": ROADMAP.replace("| M2 | not started |", "| M1 | not started |"),
            "duplicate section": ROADMAP + ROADMAP[ROADMAP.index("## M2 —"):],
            "missing section": ROADMAP[:ROADMAP.index("## M2 —")],
            "extra section": ROADMAP + ROADMAP[ROADMAP.index("## M2 —"):].replace("M2 —", "M3 —"),
            "mismatching ID": ROADMAP.replace("## M2 —", "## M3 —"),
            "wrong heading syntax": ROADMAP.replace("## M2 —", "## M2 -"),
            "malformed extra ID": ROADMAP + "\n## MX — Unexpected milestone\n",
            "unknown status": ROADMAP.replace("not started", "done"),
            "completion gap": ROADMAP.replace("| M1 | complete |", "| M1 | not started |").replace("| M2 | not started |", "| M2 | complete |"),
            "later in progress": ROADMAP.replace("| M1 | complete |", "| M1 | not started |").replace("| M2 | not started |", "| M2 | in progress |"),
            "multiple active": ROADMAP.replace("complete |", "in progress |").replace("not started |", "in progress |"),
            "missing deliverables": ROADMAP.replace("### Deliverables", "### Work", 1),
            "empty acceptance": ROADMAP.replace("Baseline passes.", ""),
            "duplicate subsection": ROADMAP.replace("Baseline passes.", "Baseline passes.\n\n### Acceptance criteria\n\nDuplicate."),
            "unterminated fence": ROADMAP + "\n```sh\nfoo\n",
            "prose inside table": ROADMAP.replace("| M2 | not started |", "| M2 | not started |\nA comment."),
        }
        for name, text in invalid.items():
            with self.subTest(name=name):
                with self.assertRaises(DiscoveryError) as caught:
                    parse_roadmap(text)
                diagnostic = caught.exception.as_dict()
                self.assertFalse(diagnostic["ok"])
                self.assertNotIn("next_milestone", diagnostic)
                self.assertIsNotNone(diagnostic["diagnostics"][0]["line"])

    def test_section_order_must_match_progress(self):
        index = ROADMAP.index("## M1 —")
        middle = ROADMAP.index("## M2 —")
        swapped = ROADMAP[:index] + ROADMAP[middle:] + "\n" + ROADMAP[index:middle]
        with self.assertRaisesRegex(DiscoveryError, "same order"):
            parse_roadmap(swapped)

    def test_stable_ids_need_not_be_contiguous(self):
        result = parse_roadmap(ROADMAP.replace("M2", "M42"))
        self.assertEqual(result.next_milestone, "M42")
