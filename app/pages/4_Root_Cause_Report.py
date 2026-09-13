from common import json_file, shell
from design import evidence_card, note, page_heading

shell("evidence_and_follow_up")
page_heading(
    "FROM OBSERVATION TO EXPERIMENT",
    "Follow the evidence.",
    "A useful finding should tell you what was observed, what remains uncertain, and how to investigate it.",
)
note(
    "Hypotheses to test",
    "These findings describe statistical associations. They are not causal or clinical conclusions.",
    "caution",
)
findings = json_file("interpretation/evidence_cards.json")
if not findings:
    note(
        "No evidence cards in this run",
        "Review the design audit and correction comparison for the available results.",
    )
for index, finding in enumerate(findings, start=1):
    evidence_card(finding, index, detailed=True)
