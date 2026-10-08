# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
import sys
sys.dont_write_bytecode = True

import unittest
from calculator import add


class AdditionTests(unittest.TestCase):
    def test_arithmetic(self):
        for a, b, expected in [(2, 3, 5), (-4, 7, 3), (0, 0, 0),
                                (1.25, 2.5, 3.75), (2, 0.5, 2.5),
                                (0.5, 2, 2.5)]:
            with self.subTest(a=a, b=b):
                self.assertEqual(add(a, b), expected)

    def test_arbitrary_precision(self):
        huge = 10 ** 1000
        self.assertEqual(add(huge, huge), 2 * huge)
        self.assertEqual(add(huge, -huge), 0)
        self.assertIsInstance(add(huge, 1), int)
        self.assertEqual(add(huge, 1), huge + 1)

    def test_invalid_types(self):
        for operand in [True, False, "2", None, [], {}, (), set(), 1j]:
            for a, b in [(operand, 1), (1, operand)]:
                with self.subTest(a=a, b=b):
                    with self.assertRaises(TypeError):
                        add(a, b)

    def test_nonfinite_operands(self):
        for operand in [float("nan"), float("inf"), -float("inf")]:
            for a, b in [(operand, 1), (1, operand)]:
                with self.subTest(a=a, b=b):
                    with self.assertRaises(ValueError):
                        add(a, b)

    def test_nonfinite_result(self):
        for a, b in [(1e308, 1e308), (-1e308, -1e308),
                     (10 ** 1000, 1.0), (1.0, 10 ** 1000)]:
            with self.subTest(a=a, b=b):
                with self.assertRaises(ValueError):
                    add(a, b)


if __name__ == "__main__":
    unittest.main()
