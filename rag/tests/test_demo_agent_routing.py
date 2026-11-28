"""Exercise CLI routing while treating any network connection as a failure."""

import subprocess
import sys
import unittest


SCRIPT = """
import sys
from unittest.mock import patch
from rag.scripts.demo_agent_routing import main

with patch("socket.socket.connect", side_effect=AssertionError("unexpected network call")):
    sys.exit(main(sys.argv[1:]))
"""


class DemoAgentRoutingTest(unittest.TestCase):
    def run_demo(self, question, *options):
        result = subprocess.run(
            [sys.executable, "-c", SCRIPT, "--query", question, *options],
            capture_output=True, text=True, check=True,
        )
        return result.stdout

    def test_questions_follow_existing_rules_without_classification(self):
        for question in (
            "갈릭디핑소스는 몇 개 주나요?",
            "맛대가리가 존나게 없어요?",
            "피자를 먹고 배가 아파요.",
        ):
            with self.subTest(question=question):
                output = self.run_demo(question)
                self.assertIn("State 변경: 없음", output)
                self.assertIn("선택된 경로: retrieve", output)
                self.assertIn("검색 실제 호출: NO", output)

    def test_existing_text_guardrail_bypasses_requested_retrieval(self):
        output = self.run_demo("주문 상태를 알려주세요.", "--with-retrieval")
        self.assertIn("선택된 경로: handoff", output)
        self.assertIn("INDIVIDUAL_ORDER", output)
        self.assertIn("검색 실제 호출: NO", output)
        output = self.run_demo("어제 주문한 피자가 아직 안 왔어요.", "--with-retrieval")
        self.assertIn("선택된 경로: handoff", output)
        self.assertIn("ACCOUNT_VERIFICATION", output)
        self.assertIn("검색 실제 호출: NO", output)

    def test_each_manual_flag_bypasses_requested_retrieval(self):
        for option in ("is-sensitive", "is-safety-related", "is-urgent", "has-individual-order-context"):
            with self.subTest(option=option):
                output = self.run_demo("맛대가리가 존나게 없어요?", "--" + option, "--with-retrieval")
                self.assertIn(f"{option.replace('-', '_')}: true (수동 입력)", output)
                self.assertIn("선택된 경로: handoff", output)
                self.assertIn("검색 실제 호출: NO", output)
