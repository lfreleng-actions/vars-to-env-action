# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 The Linux Foundation

"""Differences that come from running on Python rather than Node.js.

The include and exclude patterns are Python regular expressions, and names are
case-mapped with the Unicode data of the Python running the action. The README
lists each difference; these tests pin them, so that a change is noticed.
"""

from __future__ import annotations

import json
import unicodedata
import unittest

from tests.support import entries, entry, failure, inputs, run_action

# Vithkuqi letters arrived in Unicode 14.0; Python 3.9 and 3.10 carry 13.0.
VITHKUQI_SMALL = "\U00010597"
VITHKUQI_CAPITAL = "\U00010570"


def unicode_version() -> tuple[int, ...]:
    """Return the version of the Unicode data this Python carries."""
    return tuple(int(part) for part in unicodedata.unidata_version.split("."))


class PatternDialectTest(unittest.TestCase):
    """include and exclude compile as Python's re, not JavaScript's RegExp."""

    def test_javascript_only_syntax_is_invalid(self) -> None:
        """JavaScript-only syntax fails as an invalid pattern, exporting nothing."""
        for source in ("(?<n>a)", "(?P<n>a)\\k<n>", "(?<=a+)b"):
            with self.subTest(source=source):
                result = run_action(inputs('{"a":"1"}', include=source), outputs=True)
                self.assertEqual(
                    (result.exit_code, result.github_env, result.github_output),
                    (1, "", ""),
                )
                self.assertEqual(len(result.stdout), 2)
                prefix = f"::error::Invalid regular expression {json.dumps(source)}"
                self.assertTrue(
                    result.stdout[0].startswith(prefix + " in include: "),
                    result.stdout,
                )

    def test_python_only_syntax_compiles(self) -> None:
        """Python named groups and inline flags are accepted."""
        secrets = '{"DEPLOY_A":"1","deploy_b":"2","other":"3"}'
        for source in ("(?i)^deploy_", "^(?P<area>DEPLOY|deploy)_"):
            with self.subTest(source=source):
                result = run_action(inputs(secrets, include=source))
                self.assertEqual(
                    result.github_env, entry("DEPLOY_A", "1") + entry("DEPLOY_B", "2")
                )

    def test_whitespace_class_is_ascii(self) -> None:
        r"""\s skips U+00A0, which JavaScript counts as whitespace."""
        result = run_action(inputs('{"a\\u00a0b":"1","a b":"2"}', exclude=r"\s"))
        self.assertEqual(result.github_env, entry("A\u00a0B", "1"))

    def test_dollar_matches_before_a_final_line_feed(self) -> None:
        r"""$ also matches before a final line feed; \Z matches at the end alone."""
        secrets = '{"a\\n":"1","b":"2"}'
        excluded = run_action(inputs(secrets, exclude="^a$"))
        self.assertEqual(excluded.github_env, entry("B", "2"))
        kept = run_action(inputs(secrets, exclude="^a\\Z"))
        self.assertEqual(
            kept,
            failure(
                'Cannot export key "a\\n" as "A\\n":'
                + " the variable name contains a line feed"
            ),
        )

    def test_dot_matches_line_separators(self) -> None:
        """. matches CR, U+2028 and U+2029, which JavaScript's . does not."""
        secrets = '{"a\\rb":"1","a\\u2028b":"2","a\\u2029b":"3","c":"4"}'
        result = run_action(inputs(secrets, exclude="^a.b$"))
        self.assertEqual(result.github_env, entry("C", "4"))


class CaseMappingTest(unittest.TestCase):
    """Names are case-mapped with the Unicode data of the Python in use."""

    def test_mapping_shared_by_every_supported_python(self) -> None:
        """ASCII and the letters in the reference vectors map alike from 3.9 on."""
        secrets = (
            '{"Mixed_Case_09":"1","stra\\u00dfe":"2","\\u017f":"3",'
            + '"\\ufb01le":"4","\\u0130stanbul":"5"}'
        )
        cases = (
            ("upper", ["MIXED_CASE_09", "STRASSE", "S", "FILE", "\u0130STANBUL"]),
            (
                "lower",
                [
                    "mixed_case_09",
                    "stra\u00dfe",
                    "\u017f",
                    "\ufb01le",
                    "i\u0307stanbul",
                ],
            ),
        )
        for convert, names in cases:
            with self.subTest(convert=convert):
                result = run_action(inputs(secrets, convert=convert), outputs=True)
                outputs = entries(result.github_output or "")
                self.assertEqual(json.loads(outputs["names"]), names)

    def test_newer_letters_follow_the_unicode_version(self) -> None:
        """U+10597 upper-cases only where Python's Unicode data includes it."""
        known = unicode_version() >= (14, 0)
        expected = VITHKUQI_CAPITAL if known else VITHKUQI_SMALL
        result = run_action(inputs(json.dumps({VITHKUQI_SMALL: "1"})))
        self.assertEqual(result.github_env, entry(expected, "1"))

    def test_convert_none_skips_case_mapping(self) -> None:
        """With convert: none, no Unicode data is consulted."""
        result = run_action(inputs(json.dumps({VITHKUQI_SMALL: "1"}), convert="none"))
        self.assertEqual(result.github_env, entry(VITHKUQI_SMALL, "1"))


if __name__ == "__main__":
    _ = unittest.main()
