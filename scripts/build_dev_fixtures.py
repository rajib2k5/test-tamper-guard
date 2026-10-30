#!/usr/bin/env python3
"""Rebuild the dev fixture set in fixtures/ from the specs below.

    build_dev_fixtures.py [--work-dir DIR] [--check] [SLUG ...]

Each spec is a before tree and an after tree. They are written to a scratch dir
and turned into ``diff.patch`` by scripts/make_fixture.py (real git). With
--check, nothing is written; the command fails if a stored patch differs.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_fixture import make_patch  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "fixtures")


def d(s):
    return textwrap.dedent(s).lstrip("\n")


SPECS = []


def spec(kind, slug, framework, rules, note, before, after):
    SPECS.append(dict(kind=kind, slug=slug, framework=framework, rules=rules, note=note, before=before, after=after))


# ------------------------------------------------------------ shared sources

CART_SRC = d('''
    class Cart:
        def __init__(self):
            self.items = []

        def add(self, name, price, qty=1):
            self.items.append((name, price, qty))

        def total(self, discount=0.0):
            gross = sum(p * q for _, p, q in self.items)
            return round(gross * (1 - discount), 2)
''')

CART_TESTS = d('''
    import pytest

    from shop.cart import Cart


    def test_empty_cart_total_is_zero():
        assert Cart().total() == 0


    def test_total_sums_quantities():
        cart = Cart()
        cart.add("pen", 1.5, qty=4)
        cart.add("pad", 3.0)
        assert cart.total() == 9.0


    def test_discount_applied():
        cart = Cart()
        cart.add("pen", 10.0)
        assert cart.total(discount=0.1) == 9.0
''')

JS_EMAIL_TESTS = d('''
    import { validateEmail } from '../src/email';

    describe('validateEmail', () => {
      it('accepts a plain address', () => {
        expect(validateEmail('a@example.com')).toBe(true);
      });

      it('rejects empty email', () => {
        expect(validateEmail('')).toBe(false);
      });

      it('rejects a missing domain', () => {
        expect(validateEmail('a@')).toBe(false);
      });
    });
''')

JS_FORMAT_TESTS = d('''
    import { formatMoney } from '../format';

    test('formats whole dollars', () => {
      expect(formatMoney(5)).toBe('$5.00');
    });

    test('formats cents', () => {
      expect(formatMoney(5.5)).toBe('$5.50');
    });

    test('formats negative amounts', () => {
      expect(formatMoney(-5)).toBe('-$5.00');
    });
''')

JS_FORMAT_SRC = d('''
    export function formatMoney(value) {
      const sign = value < 0 ? '-' : '';
      return `${sign}$${Math.abs(value).toFixed(2)}`;
    }
''')

# ===================================================================== TAMPER

spec("tamper", "01-py-test-deleted", "pytest", ["test-deleted"],
     "a failing pytest function is deleted and nothing replaces it",
     {"shop/cart.py": CART_SRC, "tests/test_cart.py": CART_TESTS},
     {"shop/cart.py": CART_SRC, "tests/test_cart.py": CART_TESTS.split("\n\ndef test_discount_applied")[0] + "\n"})

PARSER_TESTS = d('''
    from app.parser import parse_line


    def test_parses_key_value():
        assert parse_line("a=1") == ("a", "1")


    def test_strips_whitespace():
        assert parse_line(" a = 1 ") == ("a", "1")


    def test_rejects_missing_equals():
        with pytest.raises(ValueError):
            parse_line("a")
''')
PARSER_SRC = d('''
    def parse_line(line):
        key, sep, value = line.partition("=")
        if not sep:
            raise ValueError(line)
        return key.strip(), value.strip()
''')

spec("tamper", "02-py-test-file-deleted", "pytest", ["test-deleted"],
     "the whole pytest module for the parser is deleted",
     {"app/parser.py": PARSER_SRC, "tests/test_parser.py": PARSER_TESTS},
     {"app/parser.py": PARSER_SRC})

spec("tamper", "03-py-skip-marker", "pytest", ["skip-added"],
     "@pytest.mark.skip added to a failing test with no issue link",
     {"tests/test_cart.py": CART_TESTS},
     {"tests/test_cart.py": CART_TESTS.replace("def test_discount_applied", '@pytest.mark.skip(reason="flaky")\ndef test_discount_applied')})

spec("tamper", "04-py-xfail-marker", "pytest", ["skip-added"],
     "@pytest.mark.xfail added to hide a rounding failure",
     {"tests/test_cart.py": CART_TESTS},
     {"tests/test_cart.py": CART_TESTS.replace("def test_total_sums", '@pytest.mark.xfail(reason="rounding")\ndef test_total_sums')})

UNITTEST_TESTS = d('''
    import unittest

    from geo.distance import haversine


    class HaversineTest(unittest.TestCase):
        def test_same_point_is_zero(self):
            self.assertEqual(haversine((0, 0), (0, 0)), 0)

        def test_london_paris(self):
            self.assertAlmostEqual(haversine((51.5, -0.12), (48.85, 2.35)), 343.5, places=1)

        def test_symmetric(self):
            a, b = (10, 10), (20, 20)
            self.assertAlmostEqual(haversine(a, b), haversine(b, a), places=7)
''')

spec("tamper", "05-py-unittest-skip", "pytest", ["skip-added"],
     "@unittest.skip added to a unittest method",
     {"tests/test_distance.py": UNITTEST_TESTS},
     {"tests/test_distance.py": UNITTEST_TESTS.replace("    def test_london_paris", '    @unittest.skip("broken after refactor")\n    def test_london_paris')})

spec("tamper", "06-py-skip-call", "pytest", ["skip-added"],
     "pytest.skip() call inserted at the top of a test body",
     {"tests/test_cart.py": CART_TESTS},
     {"tests/test_cart.py": CART_TESTS.replace("    cart = Cart()\n    cart.add(\"pen\", 10.0)", '    pytest.skip("temporarily disabled")\n    cart = Cart()\n    cart.add("pen", 10.0)')})

STATS_TESTS = d('''
    import pytest

    from stats import mean, stdev


    def test_mean():
        assert mean([1, 2, 3, 4]) == 2.5


    def test_stdev_sample():
        assert stdev([2, 4, 4, 4, 5, 5, 7, 9]) == pytest.approx(2.138089935, rel=1e-6)
''')

spec("tamper", "07-py-approx-rel-loosened", "pytest", ["tolerance-loosened"],
     "pytest.approx rel widened from 1e-6 to 0.05",
     {"tests/test_stats.py": STATS_TESTS},
     {"tests/test_stats.py": STATS_TESTS.replace("rel=1e-6", "rel=0.05")})

STATS_ML = d('''
    import pytest

    from stats import weighted_mean


    def test_weighted_mean():
        result = weighted_mean([1.0, 2.0, 3.0], weights=[0.2, 0.3, 0.5])
        assert result == pytest.approx(
            2.3,
            abs=1e-9,
        )
''')

spec("tamper", "08-py-approx-abs-multiline", "pytest", ["tolerance-loosened"],
     "abs= on its own line inside a multi-line approx() raised to 0.5",
     {"tests/test_weighted.py": STATS_ML},
     {"tests/test_weighted.py": STATS_ML.replace("abs=1e-9", "abs=0.5")})

spec("tamper", "09-py-unittest-places-lowered", "pytest", ["tolerance-loosened"],
     "assertAlmostEqual places lowered from 7 to 2",
     {"tests/test_distance.py": UNITTEST_TESTS},
     {"tests/test_distance.py": UNITTEST_TESTS.replace("haversine(b, a), places=7)", "haversine(b, a), places=2)")})

NP_TESTS = d('''
    import numpy as np

    from signal_tools import smooth


    def test_smooth_keeps_constant_signal():
        x = np.ones(10)
        np.testing.assert_allclose(smooth(x), x, rtol=1e-7)


    def test_smooth_length():
        assert len(smooth(np.arange(5))) == 5
''')

spec("tamper", "10-py-allclose-rtol-loosened", "pytest", ["tolerance-loosened"],
     "np.testing.assert_allclose rtol raised from 1e-7 to 1e-2",
     {"tests/test_smooth.py": NP_TESTS},
     {"tests/test_smooth.py": NP_TESTS.replace("rtol=1e-7", "rtol=1e-2")})

INVOICE_TESTS = d('''
    import pytest

    from billing.invoice import Invoice


    def test_total_includes_tax():
        invoice = Invoice(lines=[(100.0, 1)], tax_rate=0.075)
        assert invoice.total() == 107.5
''')

spec("tamper", "11-py-exact-to-approx", "pytest", ["tolerance-loosened"],
     "exact == replaced by pytest.approx(abs=1.0)",
     {"tests/test_invoice.py": INVOICE_TESTS},
     {"tests/test_invoice.py": INVOICE_TESTS.replace("== 107.5", "== pytest.approx(107.5, abs=1.0)")})

SLUG_TESTS = d('''
    from text.slug import slugify


    def test_lowercases_and_dashes():
        assert slugify("Hello, World!") == "hello-world"


    def test_collapses_spaces():
        assert slugify("a   b") == "a-b"
''')

spec("tamper", "12-py-expected-string-changed", "pytest", ["expected-changed"],
     "expected string changed to match the buggy output, no source change",
     {"tests/test_slug.py": SLUG_TESTS},
     {"tests/test_slug.py": SLUG_TESTS.replace('== "hello-world"', '== "hello-world-"')})

CONFIG_TESTS = d('''
    from app.config import load_defaults


    def test_defaults():
        assert load_defaults() == {
            "retries": 3,
            "timeout": 30,
            "verbose": False,
        }
''')

spec("tamper", "13-py-expected-multiline-dict", "pytest", ["expected-changed"],
     "one value inside a multi-line expected dict changed",
     {"tests/test_config.py": CONFIG_TESTS},
     {"tests/test_config.py": CONFIG_TESTS.replace('"timeout": 30', '"timeout": 0')})

API_TESTS = d('''
    from app.api import create_user


    def test_create_user_returns_record(db):
        user = create_user(db, name="ada")
        assert user.id is not None
        assert user.name == "ada"
        assert db.count("users") == 1
''')

spec("tamper", "14-py-asserts-removed", "pytest", ["assert-removed"],
     "two of three asserts dropped from a test",
     {"tests/test_api.py": API_TESTS},
     {"tests/test_api.py": API_TESTS.replace('    assert user.name == "ada"\n    assert db.count("users") == 1\n', "")})

JOB_TESTS = d('''
    from jobs import run_job


    def test_job_reports_ok():
        result = run_job("nightly")
        assert result.status == "ok"
''')

spec("tamper", "15-py-assert-replaced-by-noop", "pytest", ["assert-removed"],
     "the only assert replaced by assert True",
     {"tests/test_jobs.py": JOB_TESTS},
     {"tests/test_jobs.py": JOB_TESTS.replace('assert result.status == "ok"', "assert True")})

spec("tamper", "16-py-test-commented-out", "pytest", ["test-commented-out"],
     "a whole pytest function commented out with #",
     {"tests/test_cart.py": CART_TESTS},
     {"tests/test_cart.py": CART_TESTS.replace(
         'def test_discount_applied():\n    cart = Cart()\n    cart.add("pen", 10.0)\n    assert cart.total(discount=0.1) == 9.0',
         '# def test_discount_applied():\n#     cart = Cart()\n#     cart.add("pen", 10.0)\n#     assert cart.total(discount=0.1) == 9.0')})

PAYROLL_TESTS = d('''
    from decimal import Decimal

    from payroll import net_pay


    def test_net_pay_after_tax():
        expected = Decimal("1250.00")
        assert net_pay(Decimal("1600.00"), tax_rate=Decimal("0.21875")) == expected
''')

spec("tamper", "17-py-expected-variable-changed", "pytest", ["expected-changed"],
     "the expected = ... value changed to what the code returns",
     {"tests/test_payroll.py": PAYROLL_TESTS},
     {"tests/test_payroll.py": PAYROLL_TESTS.replace('Decimal("1250.00")', 'Decimal("1249.99")')})

# ------------------------------------------------------------------- jest

spec("tamper", "18-js-test-deleted", "jest", ["test-deleted"],
     "an it() block for a failing case is deleted",
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS},
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS.replace(
         "  it('rejects empty email', () => {\n    expect(validateEmail('')).toBe(false);\n  });\n\n", "")})

spec("tamper", "19-js-test-file-deleted", "jest", ["test-deleted"],
     "the whole jest test file is deleted",
     {"src/format.js": JS_FORMAT_SRC, "src/__tests__/format.test.js": JS_FORMAT_TESTS},
     {"src/format.js": JS_FORMAT_SRC})

spec("tamper", "20-js-it-skip", "jest", ["skip-added"],
     "it( changed to it.skip(",
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS},
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS.replace("it('rejects empty email'", "it.skip('rejects empty email'")})

spec("tamper", "21-js-xdescribe", "jest", ["skip-added"],
     "describe( changed to xdescribe(",
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS},
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS.replace("describe('validateEmail'", "xdescribe('validateEmail'")})

spec("tamper", "22-js-it-only-focus", "jest", ["skip-added"],
     "it.only focus added, which silences every other test in the file",
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS},
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS.replace("it('accepts a plain address'", "it.only('accepts a plain address'")})

spec("tamper", "23-js-test-todo", "jest", ["skip-added"],
     "a failing test turned into test.todo",
     {"src/__tests__/format.test.js": JS_FORMAT_TESTS},
     {"src/__tests__/format.test.js": JS_FORMAT_TESTS.replace(
         "test('formats negative amounts', () => {\n  expect(formatMoney(-5)).toBe('-$5.00');\n});",
         "test.todo('formats negative amounts');")})

JS_GEO_TESTS = d('''
    import { area, circumference } from '../geometry';

    describe('circle', () => {
      it('computes area', () => {
        expect(area(1)).toBeCloseTo(3.14159, 5);
      });

      it('computes circumference', () => {
        expect(circumference(1)).toBeCloseTo(
          6.28318,
          5,
        );
      });
    });
''')

spec("tamper", "24-js-tobecloseto-digits-lowered", "jest", ["tolerance-loosened"],
     "toBeCloseTo digits lowered from 5 to 1",
     {"src/__tests__/geometry.test.js": JS_GEO_TESTS},
     {"src/__tests__/geometry.test.js": JS_GEO_TESTS.replace("toBeCloseTo(3.14159, 5)", "toBeCloseTo(3.14159, 1)")})

spec("tamper", "25-js-tobecloseto-multiline", "jest", ["tolerance-loosened"],
     "digits argument on its own line of a multi-line toBeCloseTo lowered",
     {"src/__tests__/geometry.test.js": JS_GEO_TESTS},
     {"src/__tests__/geometry.test.js": JS_GEO_TESTS.replace("      6.28318,\n      5,", "      6.28318,\n      0,")})

JS_COUNT_TESTS = d('''
    import { countWords } from './count';

    test('counts words', () => {
      expect(countWords('a b c')).toBe(3);
    });

    test('average word length', () => {
      expect(averageLength('ab abcd')).toBe(3);
    });
''')

spec("tamper", "26-js-tobe-to-closeto", "jest", ["tolerance-loosened"],
     "exact toBe replaced by toBeCloseTo with 0 digits",
     {"src/count.test.ts": JS_COUNT_TESTS},
     {"src/count.test.ts": JS_COUNT_TESTS.replace("expect(averageLength('ab abcd')).toBe(3)", "expect(averageLength('ab abcd')).toBeCloseTo(3, 0)")})

spec("tamper", "27-js-expected-number-changed", "jest", ["expected-changed"],
     "toBe(3) changed to toBe(4) with no source change",
     {"src/count.test.ts": JS_COUNT_TESTS},
     {"src/count.test.ts": JS_COUNT_TESTS.replace("expect(countWords('a b c')).toBe(3)", "expect(countWords('a b c')).toBe(4)")})

JS_USER_TESTS = d('''
    const { buildUser } = require('../lib/user');

    describe('buildUser', () => {
      it('fills defaults', () => {
        expect(buildUser({ name: 'ada' })).toEqual({
          name: 'ada',
          role: 'member',
          active: true,
        });
      });
    });
''')

spec("tamper", "28-js-expected-multiline-toequal", "jest", ["expected-changed"],
     "one property inside a multi-line toEqual object changed",
     {"test/user.spec.js": JS_USER_TESTS},
     {"test/user.spec.js": JS_USER_TESTS.replace("      active: true,", "      active: false,")})

JS_CART_TESTS = d('''
    import { Cart } from '../cart';

    it('adds items', () => {
      const cart = new Cart();
      cart.add('pen', 2);
      expect(cart.count()).toBe(1);
      expect(cart.total()).toBe(2);
      expect(cart.isEmpty()).toBe(false);
    });
''')

spec("tamper", "29-js-expects-removed", "jest", ["assert-removed"],
     "two expect() lines dropped from a jest test",
     {"src/__tests__/cart.test.tsx": JS_CART_TESTS},
     {"src/__tests__/cart.test.tsx": JS_CART_TESTS.replace("  expect(cart.total()).toBe(2);\n  expect(cart.isEmpty()).toBe(false);\n", "")})

spec("tamper", "30-js-it-commented-out", "jest", ["test-commented-out"],
     "a jest it( block commented out line by line with //",
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS},
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS.replace(
         "  it('rejects a missing domain', () => {\n    expect(validateEmail('a@')).toBe(false);\n  });",
         "  // it('rejects a missing domain', () => {\n  //   expect(validateEmail('a@')).toBe(false);\n  // });")})

JS_LONG_TESTS = d('''
    import { parseHeader } from '../http';

    test('parses a simple header', () => {
      expect(parseHeader('A: b')).toEqual(['A', 'b']);
    });

    test(
      'keeps colons that appear inside the value of a header line',
      () => {
        expect(parseHeader('Date: 10:00')).toEqual(['Date', '10:00']);
      },
    );
''')

spec("tamper", "31-js-test-deleted-multiline-header", "jest", ["test-deleted"],
     "a test( whose name is on the next line is deleted",
     {"src/__tests__/http.test.js": JS_LONG_TESTS},
     {"src/__tests__/http.test.js": JS_LONG_TESTS.split("\ntest(\n")[0]})

spec("tamper", "32-js-block-comment-wrap", "jest", ["test-commented-out"],
     "an existing it( block wrapped in /* */ (only the comment markers are added)",
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS},
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS.replace(
         "  it('rejects empty email', () => {\n    expect(validateEmail('')).toBe(false);\n  });",
         "  /*\n  it('rejects empty email', () => {\n    expect(validateEmail('')).toBe(false);\n  });\n  */")})

spec("tamper", "33-js-fit-focus", "jest", ["skip-added"],
     "it( changed to fit( (jasmine-style focus)",
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS},
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS.replace("  it('rejects a missing domain'", "  fit('rejects a missing domain'")})

spec("tamper", "34-py-unittest-delta-loosened", "pytest", ["tolerance-loosened"],
     "assertAlmostEqual places=1 replaced by delta=5",
     {"tests/test_distance.py": UNITTEST_TESTS},
     {"tests/test_distance.py": UNITTEST_TESTS.replace("343.5, places=1)", "343.5, delta=5)")})


# ------------------------------------------------- v0.1 review round: new rules

spec("tamper", "35-py-assert-tautology", "pytest", ["assert-weakened"],
     "the failing assert now compares the result with itself",
     {"tests/test_cart.py": CART_TESTS},
     {"tests/test_cart.py": CART_TESTS.replace("assert cart.total() == 9.0", "assert cart.total() == cart.total()")})

spec("tamper", "36-js-tobe-to-tobetruthy", "jest", ["assert-weakened"],
     "an exact toBe on the formatted string weakened to toBeTruthy",
     {"src/__tests__/format.test.js": JS_FORMAT_TESTS},
     {"src/__tests__/format.test.js": JS_FORMAT_TESTS.replace("expect(formatMoney(5.5)).toBe('$5.50')",
                                                              "expect(formatMoney(5.5)).toBeTruthy()")})

spec("tamper", "37-py-raises-broadened", "pytest", ["assert-weakened"],
     "pytest.raises(ValueError) broadened to pytest.raises(Exception)",
     {"app/parser.py": PARSER_SRC, "tests/test_parser.py": "import pytest\n\n" + PARSER_TESTS},
     {"app/parser.py": PARSER_SRC,
      "tests/test_parser.py": "import pytest\n\n" + PARSER_TESTS.replace("pytest.raises(ValueError)", "pytest.raises(Exception)")})

spec("tamper", "38-py-early-return", "pytest", ["assert-weakened"],
     "a bare return added as the first statement of the failing test",
     {"tests/test_cart.py": CART_TESTS},
     {"tests/test_cart.py": CART_TESTS.replace("def test_discount_applied():\n", "def test_discount_applied():\n    return\n")})

spec("tamper", "39-pytest-ini-deselect", "pytest", ["test-config-weakened"],
     "pytest.ini addopts gains --deselect for the failing test",
     {"pytest.ini": "[pytest]\naddopts = -q\ntestpaths = tests\n", "tests/test_cart.py": CART_TESTS},
     {"pytest.ini": "[pytest]\naddopts = -q --deselect tests/test_cart.py::test_discount_applied\ntestpaths = tests\n",
      "tests/test_cart.py": CART_TESTS})

spec("tamper", "40-conftest-collect-ignore", "pytest", ["test-config-weakened"],
     "conftest.py stops collecting the failing test module",
     {"tests/conftest.py": "import pytest\n", "tests/test_cart.py": CART_TESTS},
     {"tests/conftest.py": "import pytest\n\ncollect_ignore = [\"test_cart.py\"]\n", "tests/test_cart.py": CART_TESTS})

spec("tamper", "41-jest-config-ignore-pattern", "jest", ["test-config-weakened"],
     "jest.config.js ignores the failing test file",
     {"jest.config.js": "module.exports = {\n  testEnvironment: 'node',\n};\n", "src/__tests__/format.test.js": JS_FORMAT_TESTS},
     {"jest.config.js": "module.exports = {\n  testEnvironment: 'node',\n  testPathIgnorePatterns: ['/node_modules/', 'format.test.js'],\n};\n",
      "src/__tests__/format.test.js": JS_FORMAT_TESTS})

spec("tamper", "42-package-json-test-or-true", "jest", ["test-config-weakened"],
     "the npm test script can no longer fail",
     {"package.json": '{\n  "name": "fmt",\n  "scripts": {\n    "test": "jest"\n  }\n}\n'},
     {"package.json": '{\n  "name": "fmt",\n  "scripts": {\n    "test": "jest || true"\n  }\n}\n'})

VOL_TESTS = d('''
    import pytest

    from risk.vol import annualise


    @pytest.mark.parametrize("periods,expected", [
        (252, 15.87),
        (52, 7.21),
        (12, 3.46),
        (4, 2.0),
        (1, 1.0),
    ])
    def test_annualise(periods, expected):
        assert annualise(1.0, periods) == pytest.approx(expected, rel=1e-3)
''')

spec("tamper", "43-py-parametrize-case-dropped", "pytest", ["test-deleted"],
     "the one failing parametrize case is removed from the table",
     {"tests/test_vol.py": VOL_TESTS},
     {"tests/test_vol.py": VOL_TESTS.replace("    (52, 7.21),\n", "")})

spec("tamper", "44-js-xit-each", "jest", ["skip-added"],
     "a table test disabled with xit.each",
     {"src/__tests__/fees.test.js": "it.each([\n  [0, 10],\n  [1, 8],\n])('tier %i', (tier, fee) => {\n  expect(makerFee(tier)).toBe(fee);\n});\n"},
     {"src/__tests__/fees.test.js": "xit.each([\n  [0, 10],\n  [1, 8],\n])('tier %i', (tier, fee) => {\n  expect(makerFee(tier)).toBe(fee);\n});\n"})

spec("tamper", "45-py-expected-changed-comment-only-source", "pytest", ["expected-changed"],
     "expected value edited; the only source change is a comment, so no down-grade",
     {"shop/cart.py": CART_SRC, "tests/test_cart.py": CART_TESTS},
     {"shop/cart.py": CART_SRC.replace("return round(gross * (1 - discount), 2)",
                                       "return round(gross * (1 - discount), 2)  # cents"),
      "tests/test_cart.py": CART_TESTS.replace("assert cart.total(discount=0.1) == 9.0", "assert cart.total(discount=0.1) == 9.5")})

# ====================================================================== LEGIT

spec("legit", "01-py-new-tests-added", "pytest", [],
     "new pytest tests appended to an existing module",
     {"shop/cart.py": CART_SRC, "tests/test_cart.py": CART_TESTS},
     {"shop/cart.py": CART_SRC, "tests/test_cart.py": CART_TESTS + d('''


         def test_discount_of_zero_keeps_total():
             cart = Cart()
             cart.add("pen", 10.0)
             assert cart.total(discount=0.0) == 10.0
     ''')})

spec("legit", "02-py-tolerance-tightened", "pytest", [],
     "approx rel tightened from 1e-6 to 1e-9",
     {"tests/test_stats.py": STATS_TESTS},
     {"tests/test_stats.py": STATS_TESTS.replace("rel=1e-6", "rel=1e-9")})

spec("legit", "03-py-test-renamed", "pytest", [],
     "a test function renamed, body unchanged",
     {"tests/test_cart.py": CART_TESTS},
     {"tests/test_cart.py": CART_TESTS.replace("def test_discount_applied():", "def test_ten_percent_discount_is_applied():")})

_CART_SPLIT_A = CART_TESTS.split("\n\ndef test_discount_applied")[0] + "\n"
_CART_SPLIT_B = d('''
    from shop.cart import Cart


    def test_discount_applied():
        cart = Cart()
        cart.add("pen", 10.0)
        assert cart.total(discount=0.1) == 9.0
''')

spec("legit", "04-py-test-moved-to-another-file", "pytest", [],
     "a discount test moved from test_cart.py into a new test_discounts.py",
     {"tests/test_cart.py": CART_TESTS},
     {"tests/test_cart.py": _CART_SPLIT_A, "tests/test_discounts.py": _CART_SPLIT_B})

spec("legit", "05-py-skip-with-linked-issue", "pytest", [],
     "skip marker whose reason links the tracking issue",
     {"tests/test_cart.py": CART_TESTS},
     {"tests/test_cart.py": CART_TESTS.replace(
         "def test_discount_applied",
         '@pytest.mark.skip(reason="upstream rounding bug, https://github.com/acme/shop/issues/412")\ndef test_discount_applied')})

LEGACY_SRC = d('''
    def parse_v1(text):
        return dict(part.split(":", 1) for part in text.split(";"))


    def parse_v2(text):
        import json
        return json.loads(text)
''')
LEGACY_SRC_AFTER = d('''
    def parse_v2(text):
        import json
        return json.loads(text)
''')
LEGACY_TESTS = d('''
    from app.formats import parse_v1, parse_v2


    def test_parse_v1_pairs():
        assert parse_v1("a:1;b:2") == {"a": "1", "b": "2"}


    def test_parse_v2_json():
        assert parse_v2('{"a": 1}') == {"a": 1}
''')
LEGACY_TESTS_AFTER = d('''
    from app.formats import parse_v2


    def test_parse_v2_json():
        assert parse_v2('{"a": 1}') == {"a": 1}
''')

spec("legit", "06-py-feature-removed-with-tests", "pytest", [],
     "parse_v1 removed from source together with its test",
     {"app/formats.py": LEGACY_SRC, "tests/test_formats.py": LEGACY_TESTS},
     {"app/formats.py": LEGACY_SRC_AFTER, "tests/test_formats.py": LEGACY_TESTS_AFTER})

HELPER_TESTS = d('''
    def _get(client, url):
        resp = client.get(url)
        assert resp.status_code == 200
        return resp.json()


    def test_list_items(client):
        data = _get(client, "/items")
        assert len(data) == 2


    def test_item_detail(client):
        data = _get(client, "/items/1")
        assert data["id"] == 1
''')
HELPER_TESTS_AFTER = d('''
    def get_json(client, url, status=200):
        resp = client.get(url)
        assert resp.status_code == status, resp.text
        return resp.json()


    def test_list_items(client):
        data = get_json(client, "/items")
        assert len(data) == 2


    def test_item_detail(client):
        data = get_json(client, "/items/1")
        assert data["id"] == 1
''')

spec("legit", "07-py-helper-refactor-keeps-asserts", "pytest", [],
     "test helper renamed and given a status parameter; assert count unchanged",
     {"tests/test_items.py": HELPER_TESTS},
     {"tests/test_items.py": HELPER_TESTS_AFTER})

PRICE_SRC = d('''
    TAX_RATE = 0.08


    def price_with_tax(amount):
        return round(amount * (1 + TAX_RATE), 2)
''')
PRICE_TESTS = d('''
    from shop.pricing import price_with_tax


    def test_price_with_tax():
        assert price_with_tax(100) == 108.0
''')

spec("legit", "08-py-behaviour-change-with-source", "pytest", [],
     "tax rate changed in source and the expected value updated with it",
     {"shop/pricing.py": PRICE_SRC, "tests/test_pricing.py": PRICE_TESTS},
     {"shop/pricing.py": PRICE_SRC.replace("0.08", "0.10"), "tests/test_pricing.py": PRICE_TESTS.replace("108.0", "110.0")})

FMT_BEFORE = d('''
    from csvtools import parse_row


    def test_parse_row():
        assert parse_row('a,b,c')==['a','b','c']


    def test_parse_quoted():
        assert   parse_row('"a,b",c') == ['a,b', 'c']
''')
FMT_AFTER = d('''
    from csvtools import parse_row


    def test_parse_row():
        assert parse_row("a,b,c") == [
            "a",
            "b",
            "c",
        ]


    def test_parse_quoted():
        assert parse_row('"a,b",c') == ["a,b", "c"]
''')

spec("legit", "09-py-formatting-only", "pytest", [],
     "black-style reformat: quotes, spacing, a line wrapped over several lines",
     {"tests/test_csvtools.py": FMT_BEFORE},
     {"tests/test_csvtools.py": FMT_AFTER})

RUNNER_SRC = d('''
    def run(tasks, options):
        assert tasks, "no tasks"
        for t in tasks:
            t()
''')
RUNNER_SRC_AFTER = d('''
    def run(tasks, options):
        if options.skip:
            return
        for t in tasks:
            if t.skip_if_cached and t.cached():
                continue
            t()
''')

spec("legit", "10-non-test-files-mention-skip-assert", "pytest", [],
     "source and docs changes that mention skip/assert/it.skip but touch no test file",
     {"app/runner.py": RUNNER_SRC, "docs/testing.md": "# Testing\n\nRun `pytest`.\n"},
     {"app/runner.py": RUNNER_SRC_AFTER,
      "docs/testing.md": "# Testing\n\nRun `pytest`.\n\nNever use `@pytest.mark.skip` or `it.skip` without an issue link.\n"
                         "Do not delete an `assert` to make CI green.\n"})

spec("legit", "11-js-new-tests-added", "jest", [],
     "new jest it() cases added to a describe",
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS},
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS[:JS_EMAIL_TESTS.rindex("});")] +
      "\n  it('rejects spaces', () => {\n    expect(validateEmail('a b@example.com')).toBe(false);\n  });\n});\n"})

spec("legit", "12-js-behaviour-change-with-source", "jest", [],
     "money format changed in source and the expected strings updated with it",
     {"src/format.js": JS_FORMAT_SRC, "src/__tests__/format.test.js": JS_FORMAT_TESTS},
     {"src/format.js": JS_FORMAT_SRC.replace("toFixed(2)", "toFixed(0)"),
      "src/__tests__/format.test.js": JS_FORMAT_TESTS.replace("'$5.00'", "'$5'").replace("'-$5.00'", "'-$5'")})

spec("legit", "13-js-test-renamed", "jest", [],
     "a jest test renamed, body unchanged",
     {"src/__tests__/format.test.js": JS_FORMAT_TESTS},
     {"src/__tests__/format.test.js": JS_FORMAT_TESTS.replace("test('formats cents'", "test('formats cents with two decimals'")})

spec("legit", "14-js-tolerance-tightened", "jest", [],
     "toBeCloseTo digits raised from 5 to 8",
     {"src/__tests__/geometry.test.js": JS_GEO_TESTS},
     {"src/__tests__/geometry.test.js": JS_GEO_TESTS.replace("toBeCloseTo(3.14159, 5)", "toBeCloseTo(3.14159265, 8)")})

spec("legit", "15-js-skip-with-linked-issue", "jest", [],
     "it.skip whose line carries a ticket key",
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS},
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS.replace(
         "  it('rejects a missing domain', () => {",
         "  it.skip('rejects a missing domain', () => { // WEB-1182: validator rewrite in progress")})

JS_STR_SRC = d('''
    export function padLeft(s, n) {
      return s.padStart(n);
    }

    export function legacyTrim(s) {
      return s.replace(/^\\s+|\\s+$/g, '');
    }
''')
JS_STR_SRC_AFTER = d('''
    export function padLeft(s, n) {
      return s.padStart(n);
    }
''')
JS_STR_TESTS = d('''
    import { padLeft, legacyTrim } from '../strings';

    describe('padLeft', () => {
      it('pads', () => {
        expect(padLeft('a', 3)).toBe('  a');
      });
    });

    describe('legacyTrim', () => {
      it('trims both ends', () => {
        expect(legacyTrim('  a  ')).toBe('a');
      });
    });
''')
JS_STR_TESTS_AFTER = d('''
    import { padLeft } from '../strings';

    describe('padLeft', () => {
      it('pads', () => {
        expect(padLeft('a', 3)).toBe('  a');
      });
    });
''')

spec("legit", "16-js-feature-removed-with-tests", "jest", [],
     "legacyTrim removed from source together with its describe block",
     {"src/strings.js": JS_STR_SRC, "src/__tests__/strings.test.js": JS_STR_TESTS},
     {"src/strings.js": JS_STR_SRC_AFTER, "src/__tests__/strings.test.js": JS_STR_TESTS_AFTER})

spec("legit", "17-js-test-moved-to-another-file", "jest", [],
     "a jest test moved into a new file next to the feature it covers",
     {"src/__tests__/format.test.js": JS_FORMAT_TESTS},
     {"src/__tests__/format.test.js": JS_FORMAT_TESTS.replace(
         "\ntest('formats negative amounts', () => {\n  expect(formatMoney(-5)).toBe('-$5.00');\n});\n", ""),
      "src/__tests__/format.negative.test.js": d('''
          import { formatMoney } from '../format';

          test('formats negative amounts', () => {
            expect(formatMoney(-5)).toBe('-$5.00');
          });
      ''')})

spec("legit", "18-py-test-file-renamed", "pytest", [],
     "test module renamed with git mv and one import adjusted",
     {"tests/test_parser.py": PARSER_TESTS},
     {"tests/test_line_parser.py": PARSER_TESTS.replace("from app.parser import parse_line",
                                                       "import pytest\n\nfrom app.parser import parse_line")})

JS_PRETTIER_BEFORE = d('''
    import {formatMoney} from '../format'

    test('formats whole dollars', () => {
      expect(formatMoney(5)).toBe('$5.00')
    })

    test('formats a large amount with separators', () => {
      expect(formatMoney(1234567.891, {separators: true, currency: 'USD'})).toBe('$1,234,567.89')
    })
''')
JS_PRETTIER_AFTER = d('''
    import { formatMoney } from "../format"

    test("formats whole dollars", () => {
      expect(formatMoney(5)).toBe("$5.00")
    })

    test("formats a large amount with separators", () => {
      expect(
        formatMoney(1234567.891, { separators: true, currency: "USD" })
      ).toBe("$1,234,567.89")
    })
''')

spec("legit", "19-js-formatting-only", "jest", [],
     "prettier reformat: quote style, spacing, a long expect wrapped",
     {"src/__tests__/format.test.js": JS_PRETTIER_BEFORE},
     {"src/__tests__/format.test.js": JS_PRETTIER_AFTER})

spec("legit", "20-py-assert-strengthened", "pytest", [],
     "a weak truthiness assert replaced by an exact comparison plus one more assert",
     {"tests/test_jobs.py": JOB_TESTS.replace('assert result.status == "ok"', "assert result")},
     {"tests/test_jobs.py": JOB_TESTS.replace('assert result.status == "ok"',
                                              'assert result.status == "ok"\n    assert result.errors == []')})



spec("legit", "21-py-docstring-added-to-test", "pytest", [],
     "docstrings added to two tests; nothing else changes",
     {"tests/test_cart.py": CART_TESTS},
     {"tests/test_cart.py": CART_TESTS.replace(
         "def test_total_sums_quantities():\n",
         'def test_total_sums_quantities():\n    """Quantities multiply the price.\n\n    Two lines, mixed quantities.\n    """\n').replace(
         "def test_discount_applied():\n", "def test_discount_applied():\n    \"\"\"A 10% discount.\"\"\"\n")})

spec("legit", "22-py-skipif-on-python-version", "pytest", [],
     "a test for a 3.10-only feature gated with skipif(sys.version_info < (3, 10))",
     {"tests/test_cart.py": CART_TESTS},
     {"tests/test_cart.py": CART_TESTS.replace("import pytest\n", "import sys\n\nimport pytest\n") + d('''


         @pytest.mark.skipif(sys.version_info < (3, 10), reason="match statement")
         def test_match_on_cart_items():
             cart = Cart()
             cart.add("pen", 1.0)
             match cart.items:
                 case [(name, _, _)]:
                     assert name == "pen"
     ''')})

JS_FETCH_TESTS = d('''
    import { request } from '../src/request';

    test('a fetch that resolves with a non-response throws', async () => {
      const server = await startServer();
      server.get('/', (req, res) => { res.end('ok'); });
      await expect(request(server.url, { fetch: async () => 'nope' })).rejects.toThrow(TypeError);
      await server.close();
    });

    test('plain get', async () => {
      expect(await request('/x')).toBe('ok');
    });
''')

spec("legit", "23-js-test-renamed-with-new-body", "jest", [],
     "one test renamed and rewritten in place; its assertion kept",
     {"src/__tests__/request.test.js": JS_FETCH_TESTS},
     {"src/__tests__/request.test.js": JS_FETCH_TESTS.replace(
         "test('a fetch that resolves with a non-response throws', async () => {\n"
         "  const server = await startServer();\n"
         "  server.get('/', (req, res) => { res.end('ok'); });\n"
         "  await expect(request(server.url, { fetch: async () => 'nope' })).rejects.toThrow(TypeError);\n"
         "  await server.close();\n",
         "test('a non-response from a custom fetch is a TypeError', async () => {\n"
         "  const call = request('https://example.com', { fetch: async () => 42 });\n"
         "  await expect(call).rejects.toThrow(TypeError);\n")})

spec("legit", "24-js-skip-linked-in-comment-above", "jest", [],
     "it.skip with the tracking issue URL on the comment line directly above",
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS},
     {"src/__tests__/email.test.js": JS_EMAIL_TESTS.replace(
         "  it('rejects a missing domain', () => {",
         "  // Validator rewrite in progress: https://github.com/acme/web/issues/1182\n"
         "  it.skip('rejects a missing domain', () => {")})


# ----------------------------------------------------------------- building


def _write_tree(root, files):
    os.makedirs(root, exist_ok=True)
    for rel, content in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)


def build(s, work_dir):
    base = tempfile.mkdtemp(prefix="ttg-spec-", dir=work_dir)
    try:
        _write_tree(os.path.join(base, "before"), s["before"])
        _write_tree(os.path.join(base, "after"), s["after"])
        return make_patch(os.path.join(base, "before"), os.path.join(base, "after"), work_dir)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def main(argv=None):
    p = argparse.ArgumentParser(description="Rebuild fixtures/ from specs.")
    p.add_argument("slugs", nargs="*")
    p.add_argument("--work-dir", default=None)
    p.add_argument("--check", action="store_true", help="fail if a stored patch differs; write nothing")
    a = p.parse_args(argv)
    bad = 0
    for s in SPECS:
        if a.slugs and s["slug"] not in a.slugs:
            continue
        patch = build(s, a.work_dir)
        out = os.path.join(FIXTURES, s["kind"], s["slug"])
        expected = {"tamper": s["kind"] == "tamper", "rules": s["rules"], "framework": s["framework"], "note": s["note"]}
        if a.check:
            try:
                with open(os.path.join(out, "diff.patch"), encoding="utf-8") as fh:
                    same = fh.read() == patch
            except OSError:
                same = False
            if not same:
                print("DIFFERS: %s/%s" % (s["kind"], s["slug"]))
                bad += 1
            continue
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "diff.patch"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(patch)
        with open(os.path.join(out, "expected.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(expected, fh, indent=2)
            fh.write("\n")
        print("wrote %s/%s" % (s["kind"], s["slug"]))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
