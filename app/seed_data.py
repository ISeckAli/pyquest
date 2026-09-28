"""
Starter content for PyQuest: topics and challenges loaded by
`flask --app app seed` (spec Part 12, seed data).

Each challenge has one visible test (shown as an example) and several
hidden tests covering edge cases, a reference solution, and fallback hints
that guide without giving the answer. tests/test_seed.py runs every
reference solution against its own tests, so a wrong expected output can
never be committed.

Tests are written as (input, expected output, is hidden).
"""

SEED_TOPICS = [
    {"name": "Strings", "slug": "strings", "order": 1,
     "description": "Working with text."},
    {"name": "Conditionals", "slug": "conditionals", "order": 2,
     "description": "Making decisions with if, elif, and else."},
    {"name": "Loops", "slug": "loops", "order": 3,
     "description": "Repeating work with for and while."},
]

SEED_CHALLENGES = [
    {
        "title": "Shout It",
        "topic": "strings",
        "difficulty": "beginner",
        "description": (
            "Read a line of text and print it in capital letters, followed by an "
            "exclamation mark.\n\nFor example, if the input is hi, print HI!"
        ),
        "starter": "text = input()\n# Print the text in capitals, then an exclamation mark",
        "reference": 'text = input()\nprint(text.upper() + "!")',
        "tests": [
            ("hi", "HI!", False),
            ("Python rocks", "PYTHON ROCKS!", True),
            ("a", "A!", True),
        ],
        "hints": [
            "Strings have methods that change their case.",
            "Look for a string method that turns every letter into a capital.",
            "You can join two strings together with +.",
        ],
    },
    {
        "title": "Count the Vowels",
        "topic": "strings",
        "difficulty": "beginner",
        "description": (
            "Read a line of text and print how many vowels it contains. The vowels "
            "are a, e, i, o, and u, in upper or lower case."
        ),
        "starter": "text = input()\n# Count the vowels and print the total",
        "reference": (
            "text = input()\n"
            "count = 0\n"
            "for letter in text.lower():\n"
            '    if letter in "aeiou":\n'
            "        count += 1\n"
            "print(count)"
        ),
        "tests": [
            ("hello", "2", False),
            ("PyQuest", "2", True),
            ("rhythm", "0", True),
            ("AEIOU aeiou", "10", True),
        ],
        "hints": [
            "Go through the text one letter at a time.",
            "Lowercasing the text first means you only need to check a, e, i, o, and u.",
            "Keep a counter that starts at 0 and grows by 1 for each vowel.",
        ],
    },
    {
        "title": "Even or Odd",
        "topic": "conditionals",
        "difficulty": "beginner",
        "description": "Read a whole number and print even if it is even, or odd if it is odd.",
        "starter": "number = int(input())\n# Print even or odd",
        "reference": (
            "number = int(input())\n"
            "if number % 2 == 0:\n"
            '    print("even")\n'
            "else:\n"
            '    print("odd")'
        ),
        "tests": [
            ("4", "even", False),
            ("7", "odd", True),
            ("0", "even", True),
            ("-3", "odd", True),
        ],
        "hints": [
            "An even number divides by 2 with nothing left over.",
            "The % operator gives the remainder of a division.",
        ],
    },
    {
        "title": "Letter Grade",
        "topic": "conditionals",
        "difficulty": "intermediate",
        "description": (
            "Read a score from 0 to 100 and print its letter grade: A for 90 and "
            "above, B for 80 to 89, C for 70 to 79, D for 60 to 69, and F below 60."
        ),
        "starter": "score = int(input())\n# Print the letter grade",
        "reference": (
            "score = int(input())\n"
            "if score >= 90:\n"
            '    print("A")\n'
            "elif score >= 80:\n"
            '    print("B")\n'
            "elif score >= 70:\n"
            '    print("C")\n'
            "elif score >= 60:\n"
            '    print("D")\n'
            "else:\n"
            '    print("F")'
        ),
        "tests": [
            ("85", "B", False),
            ("90", "A", True),
            ("59", "F", True),
            ("70", "C", True),
            ("100", "A", True),
        ],
        "hints": [
            "Check the highest grade first, then work your way down.",
            "if, elif, and else let you test one condition after another.",
            "Watch the boundaries: is a score of exactly 90 an A or a B?",
        ],
    },
    {
        "title": "Countdown",
        "topic": "loops",
        "difficulty": "beginner",
        "description": (
            "Read a positive whole number n. Print the numbers from n down to 1, one "
            "per line, then print Liftoff!"
        ),
        "starter": "n = int(input())\n# Count down from n to 1, then print Liftoff!",
        "reference": (
            "n = int(input())\n"
            "for number in range(n, 0, -1):\n"
            "    print(number)\n"
            'print("Liftoff!")'
        ),
        "tests": [
            ("3", "3\n2\n1\nLiftoff!", False),
            ("1", "1\nLiftoff!", True),
            ("5", "5\n4\n3\n2\n1\nLiftoff!", True),
        ],
        "hints": [
            "A loop can count backwards as well as forwards.",
            "range() can take a start, a stop, and a step. Which step counts down?",
            "The Liftoff! line comes after the loop, not inside it.",
        ],
    },
    {
        "title": "Sum of Digits",
        "topic": "loops",
        "difficulty": "intermediate",
        "description": (
            "Read a non-negative whole number and print the sum of its digits.\n\n"
            "For example, 123 gives 1 + 2 + 3 = 6."
        ),
        "starter": "digits = input()\n# Add up the digits and print the total",
        "reference": (
            "digits = input().strip()\n"
            "total = 0\n"
            "for digit in digits:\n"
            "    total += int(digit)\n"
            "print(total)"
        ),
        "tests": [
            ("123", "6", False),
            ("0", "0", True),
            ("9999", "36", True),
            ("1005", "6", True),
        ],
        "hints": [
            "The input is text, so you can loop over it one character at a time.",
            "Each character is a string; int() turns it into a number you can add.",
        ],
    },
]