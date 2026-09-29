"""
Starter content for PyQuest: topics and challenges loaded by
`flask --app app seed` (spec Part 12, seed data).

Most challenges are adapted from COMP100 (Programming 1) practice exercises
at Centennial College, reworded as input/output problems that PyQuest can
test automatically. Exercises that repeated across weeks (such as letter
grades and even or odd) appear once.

Each challenge has one visible test (shown as an example), several hidden
tests covering edge cases, a reference solution, and fallback hints that
guide without giving the answer. tests/test_seed.py runs every reference
solution against its own tests, so a wrong expected output can never be
committed.

Tests are written as (input, expected output, is hidden). Several lines of
input are separated by \n, one line per input() call.
"""

SEED_TOPICS = [
    {"name": "Variables and Input", "slug": "variables-and-input", "order": 0,
     "description": "Storing values, reading input, and converting between types."},
    {"name": "Strings", "slug": "strings", "order": 1,
     "description": "Working with text."},
    {"name": "Conditionals", "slug": "conditionals", "order": 2,
     "description": "Making decisions with if, elif, and else."},
    {"name": "Loops", "slug": "loops", "order": 3,
     "description": "Repeating work with for and while."},
    {"name": "Lists and Tuples", "slug": "lists-and-tuples", "order": 4,
     "description": "Ordered collections: indexing, sorting, and built-in functions."},
    {"name": "Match Statements", "slug": "match-statements", "order": 5,
     "description": "Choosing between cases with match and case."},
    {"name": "Sets and Dictionaries", "slug": "sets-and-dictionaries", "order": 6,
     "description": "Unique values, lookups, and counting."},
    {"name": "Errors and Exceptions", "slug": "errors-and-exceptions", "order": 7,
     "description": "Handling bad input with try and except."},
]


def challenge(title, topic, difficulty, description, starter, reference, tests, hints):
    return {
        "title": title, "topic": topic, "difficulty": difficulty,
        "description": description, "starter": starter, "reference": reference,
        "tests": tests, "hints": hints,
    }


SEED_CHALLENGES = [
    # ------------------------------------------------------------------
    # Variables and Input
    # ------------------------------------------------------------------
    challenge(
        "Weekly Pay", "variables-and-input", "beginner",
        "Read an hourly wage on the first line and the hours worked on the second. "
        "Print the total pay with exactly two decimal places.\n\n"
        "For example, 21.50 an hour for 40 hours prints 860.00",
        "wage = float(input())\nhours = float(input())\n# Print the total pay with two decimals",
        "wage = float(input())\nhours = float(input())\nprint(f\"{wage * hours:.2f}\")",
        [("21.50\n40", "860.00", False), ("17.25\n12", "207.00", True),
         ("15\n0", "0.00", True), ("20\n37.5", "750.00", True)],
        ["Pay is the wage multiplied by the hours.",
         "An f-string with :.2f shows a number with two decimal places."],
    ),
    challenge(
        "Approximate Age", "variables-and-input", "beginner",
        "Read a birth year and print the person's approximate age in 2026.",
        "birth_year = int(input())\n# Print the approximate age in 2026",
        "birth_year = int(input())\nprint(2026 - birth_year)",
        [("1995", "31", False), ("2026", "0", True), ("2000", "26", True)],
        ["input() gives text; int() turns it into a number you can subtract.",
         "The age is the current year minus the birth year."],
    ),
    challenge(
        "Rectangle Area", "variables-and-input", "beginner",
        "Read a rectangle's length on the first line and its width on the second. "
        "Print Area: followed by the area with two decimal places.\n\n"
        "For example, 5 and 3 print Area: 15.00",
        "length = float(input())\nwidth = float(input())\n# Print the area",
        "length = float(input())\nwidth = float(input())\nprint(f\"Area: {length * width:.2f}\")",
        [("5\n3", "Area: 15.00", False), ("2.5\n4", "Area: 10.00", True),
         ("0.5\n0.5", "Area: 0.25", True)],
        ["The area of a rectangle is its length times its width.",
         "Put the label and the formatted number in one f-string."],
    ),
    challenge(
        "Discounted Price", "variables-and-input", "beginner",
        "Read a price on the first line and a discount percentage on the second. "
        "Print the price after the discount, with two decimal places.\n\n"
        "For example, 200 with a 20 percent discount prints 160.00",
        "price = float(input())\ndiscount = float(input())\n# Print the discounted price",
        "price = float(input())\ndiscount = float(input())\n"
        "print(f\"{price * (1 - discount / 100):.2f}\")",
        [("200\n20", "160.00", False), ("99.99\n0", "99.99", True),
         ("50\n100", "0.00", True), ("80\n12.5", "70.00", True)],
        ["A 20 percent discount leaves 80 percent of the price.",
         "Turn the percentage into a fraction by dividing it by 100."],
    ),

    # ------------------------------------------------------------------
    # Strings
    # ------------------------------------------------------------------
    challenge(
        "Shout It", "strings", "beginner",
        "Read a line of text and print it in capital letters, followed by an "
        "exclamation mark.\n\nFor example, if the input is hi, print HI!",
        "text = input()\n# Print the text in capitals, then an exclamation mark",
        'text = input()\nprint(text.upper() + "!")',
        [("hi", "HI!", False), ("Python rocks", "PYTHON ROCKS!", True), ("a", "A!", True)],
        ["Strings have methods that change their case.",
         "Look for a string method that turns every letter into a capital.",
         "You can join two strings together with +."],
    ),
    challenge(
        "Count the Vowels", "strings", "beginner",
        "Read a line of text and print how many vowels it contains. The vowels "
        "are a, e, i, o, and u, in upper or lower case.",
        "text = input()\n# Count the vowels and print the total",
        "text = input()\ncount = 0\nfor letter in text.lower():\n"
        '    if letter in "aeiou":\n        count += 1\nprint(count)',
        [("hello", "2", False), ("PyQuest", "2", True), ("rhythm", "0", True),
         ("AEIOU aeiou", "10", True)],
        ["Go through the text one letter at a time.",
         "Lowercasing the text first means you only need to check a, e, i, o, and u.",
         "Keep a counter that starts at 0 and grows by 1 for each vowel."],
    ),
    challenge(
        "Tidy Name", "strings", "beginner",
        "Read a name that may have extra spaces and odd capitals. Print it with "
        "the spaces at each end removed and each word capitalised.\n\n"
        "For example,   narendra pershad   prints Narendra Pershad",
        "name = input()\n# Print the tidied name",
        "name = input()\nprint(name.strip().title())",
        [("  narendra pershad  ", "Narendra Pershad", False),
         ("IVAN seck ali", "Ivan Seck Ali", True), ("a", "A", True)],
        ["Strings have a method that removes spaces from both ends.",
         "Another string method capitalises the first letter of every word.",
         "String methods can be chained: one after another."],
    ),
    challenge(
        "Date Format Check", "strings", "intermediate",
        "Read a date and print valid if it is written as YYYY-MM-DD (four digits, "
        "a dash, two digits, a dash, two digits), otherwise print invalid. Only "
        "the format is checked, not whether the date exists.",
        "date = input()\n# Print valid or invalid",
        "date = input().strip()\n"
        "valid = (len(date) == 10 and date[4] == \"-\" and date[7] == \"-\"\n"
        "         and date.replace(\"-\", \"\").isdigit())\n"
        "print(\"valid\" if valid else \"invalid\")",
        [("2026-09-29", "valid", False), ("2026/09/29", "invalid", True),
         ("2026-9-29", "invalid", True), ("2026-0a-29", "invalid", True),
         ("1999-12-31", "valid", True)],
        ["Check the length first: a correct date has exactly 10 characters.",
         "The dashes must be at positions 4 and 7 (counting from 0).",
         "Without the dashes, every remaining character must be a digit."],
    ),

    # ------------------------------------------------------------------
    # Conditionals
    # ------------------------------------------------------------------
    challenge(
        "Even or Odd", "conditionals", "beginner",
        "Read a whole number and print even if it is even, or odd if it is odd.",
        "number = int(input())\n# Print even or odd",
        "number = int(input())\nif number % 2 == 0:\n    print(\"even\")\nelse:\n    print(\"odd\")",
        [("4", "even", False), ("7", "odd", True), ("0", "even", True), ("-3", "odd", True)],
        ["An even number divides by 2 with nothing left over.",
         "The % operator gives the remainder of a division."],
    ),
    challenge(
        "Letter Grade", "conditionals", "intermediate",
        "Read a score from 0 to 100 and print its letter grade: A for 90 and "
        "above, B for 80 to 89, C for 70 to 79, D for 60 to 69, and F below 60.",
        "score = int(input())\n# Print the letter grade",
        "score = int(input())\nif score >= 90:\n    print(\"A\")\nelif score >= 80:\n"
        "    print(\"B\")\nelif score >= 70:\n    print(\"C\")\nelif score >= 60:\n"
        "    print(\"D\")\nelse:\n    print(\"F\")",
        [("85", "B", False), ("90", "A", True), ("59", "F", True), ("70", "C", True),
         ("100", "A", True)],
        ["Check the highest grade first, then work your way down.",
         "if, elif, and else let you test one condition after another.",
         "Watch the boundaries: is a score of exactly 90 an A or a B?"],
    ),
    challenge(
        "Leap Year", "conditionals", "intermediate",
        "Read a year and print Leap year or Not a leap year. A year is a leap "
        "year if it divides by 4 but not by 100, or if it divides by 400.",
        "year = int(input())\n# Print Leap year or Not a leap year",
        "year = int(input())\n"
        "if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0:\n"
        "    print(\"Leap year\")\nelse:\n    print(\"Not a leap year\")",
        [("2024", "Leap year", False), ("2000", "Leap year", True),
         ("1900", "Not a leap year", True), ("2023", "Not a leap year", True)],
        ["% tells you whether one number divides another evenly.",
         "and and or let you combine conditions; brackets make the grouping clear.",
         "Try 1900 and 2000 by hand: they are the tricky cases."],
    ),
    challenge(
        "Positive, Negative, or Zero", "conditionals", "beginner",
        "Read a number (it may have decimals) and print positive, negative, or zero.",
        "number = float(input())\n# Print positive, negative, or zero",
        "number = float(input())\nif number > 0:\n    print(\"positive\")\n"
        "elif number == 0:\n    print(\"zero\")\nelse:\n    print(\"negative\")",
        [("7", "positive", False), ("0", "zero", True), ("-3", "negative", True),
         ("-0.5", "negative", True)],
        ["There are three possible answers, so you need three branches.",
         "Compare the number with 0 using >, ==, or <."],
    ),
    challenge(
        "Smallest of Three", "conditionals", "beginner",
        "Read three whole numbers, one per line, and print the smallest.",
        "a = int(input())\nb = int(input())\nc = int(input())\n# Print the smallest",
        "a = int(input())\nb = int(input())\nc = int(input())\n"
        "if a <= b and a <= c:\n    print(a)\nelif b <= c:\n    print(b)\nelse:\n    print(c)",
        [("4\n9\n2", "2", False), ("5\n5\n7", "5", True), ("-1\n-8\n0", "-8", True)],
        ["A number is the smallest if it is less than or equal to both others.",
         "Using <= rather than < handles numbers that are equal.",
         "Python also has a built-in function that finds the smallest value."],
    ),
    challenge(
        "Valid Triangle", "conditionals", "beginner",
        "Read three side lengths, one per line. Print Valid triangle if every "
        "pair of sides adds up to more than the third side, otherwise print "
        "Not a valid triangle.",
        "a = int(input())\nb = int(input())\nc = int(input())\n# Print whether the triangle is valid",
        "a = int(input())\nb = int(input())\nc = int(input())\n"
        "if a + b > c and a + c > b and b + c > a:\n    print(\"Valid triangle\")\n"
        "else:\n    print(\"Not a valid triangle\")",
        [("3\n4\n5", "Valid triangle", False), ("1\n2\n3", "Not a valid triangle", True),
         ("5\n5\n5", "Valid triangle", True), ("10\n2\n3", "Not a valid triangle", True)],
        ["There are three pairs of sides to check.",
         "All three checks must be true at once: join them with and.",
         "\"More than\" means >, not >=."],
    ),
    challenge(
        "Shipping Category", "conditionals", "beginner",
        "Read a package weight in pounds and print its category: Lightweight up "
        "to 2, Standard up to 10, Heavy up to 100, and Freight above 100.",
        "weight = float(input())\n# Print the shipping category",
        "weight = float(input())\nif weight <= 2:\n    print(\"Lightweight\")\n"
        "elif weight <= 10:\n    print(\"Standard\")\nelif weight <= 100:\n"
        "    print(\"Heavy\")\nelse:\n    print(\"Freight\")",
        [("5", "Standard", False), ("2", "Lightweight", True), ("10", "Standard", True),
         ("100.5", "Freight", True), ("0.5", "Lightweight", True)],
        ["\"Up to 2\" includes 2 itself, so use <=.",
         "Check the lightest category first and work upwards with elif."],
    ),
    challenge(
        "Tax Bracket", "conditionals", "intermediate",
        "Read an annual income and print its tax rate: 15% up to 20,000, 20% up "
        "to 50,000, 30% up to 80,000, 40% up to 110,000, and 50% above that.",
        "income = float(input())\n# Print the tax rate, such as 20%",
        "income = float(input())\nif income <= 20_000:\n    print(\"15%\")\n"
        "elif income <= 50_000:\n    print(\"20%\")\nelif income <= 80_000:\n"
        "    print(\"30%\")\nelif income <= 110_000:\n    print(\"40%\")\nelse:\n    print(\"50%\")",
        [("45000", "20%", False), ("20000", "15%", True), ("80000.01", "40%", True),
         ("250000", "50%", True)],
        ["Each bracket's limit is included in that bracket, so use <=.",
         "Python lets you write 20_000 instead of 20000 to make large numbers readable.",
         "Print the rate as text, with the % sign included."],
    ),

    # ------------------------------------------------------------------
    # Loops
    # ------------------------------------------------------------------
    challenge(
        "Countdown", "loops", "beginner",
        "Read a positive whole number n. Print the numbers from n down to 1, one "
        "per line, then print Liftoff!",
        "n = int(input())\n# Count down from n to 1, then print Liftoff!",
        "n = int(input())\nfor number in range(n, 0, -1):\n    print(number)\nprint(\"Liftoff!\")",
        [("3", "3\n2\n1\nLiftoff!", False), ("1", "1\nLiftoff!", True),
         ("5", "5\n4\n3\n2\n1\nLiftoff!", True)],
        ["A loop can count backwards as well as forwards.",
         "range() can take a start, a stop, and a step. Which step counts down?",
         "The Liftoff! line comes after the loop, not inside it."],
    ),
    challenge(
        "Sum of Digits", "loops", "intermediate",
        "Read a non-negative whole number and print the sum of its digits.\n\n"
        "For example, 123 gives 1 + 2 + 3 = 6.",
        "digits = input()\n# Add up the digits and print the total",
        "digits = input().strip()\ntotal = 0\nfor digit in digits:\n    total += int(digit)\nprint(total)",
        [("123", "6", False), ("0", "0", True), ("9999", "36", True), ("1005", "6", True)],
        ["The input is text, so you can loop over it one character at a time.",
         "Each character is a string; int() turns it into a number you can add."],
    ),
    challenge(
        "Odd Squares", "loops", "beginner",
        "Read a whole number n (at least 1). Print the square of every odd "
        "number from 1 to n, one per line.",
        "n = int(input())\n# Print the squares of the odd numbers up to n",
        "n = int(input())\nfor number in range(1, n + 1, 2):\n    print(number * number)",
        [("5", "1\n9\n25", False), ("1", "1", True), ("8", "1\n9\n25\n49", True)],
        ["The odd numbers start at 1 and go up in steps of 2.",
         "range() stops before its end value, so think about n + 1."],
    ),
    challenge(
        "Even Numbers", "loops", "beginner",
        "Read a whole number n (at least 2). Print every even number from 2 up "
        "to n, one per line.",
        "n = int(input())\n# Print the even numbers from 2 to n",
        "n = int(input())\nfor number in range(2, n + 1, 2):\n    print(number)",
        [("10", "2\n4\n6\n8\n10", False), ("3", "2", True), ("2", "2", True)],
        ["The even numbers start at 2 and go up in steps of 2.",
         "Should n itself be printed when it is even?"],
    ),

    # ------------------------------------------------------------------
    # Lists and Tuples
    # ------------------------------------------------------------------
    challenge(
        "Min, Max, and Sum", "lists-and-tuples", "beginner",
        "Read whole numbers on one line, separated by spaces. Print the smallest, "
        "the largest, and the total, each on its own line as shown:\n\n"
        "min: 2\nmax: 10\nsum: 29",
        "numbers = [int(n) for n in input().split()]\n# Print min, max, and sum",
        "numbers = [int(n) for n in input().split()]\n"
        "print(f\"min: {min(numbers)}\")\nprint(f\"max: {max(numbers)}\")\n"
        "print(f\"sum: {sum(numbers)}\")",
        [("8 3 10 2 6", "min: 2\nmax: 10\nsum: 29", False), ("5", "min: 5\nmax: 5\nsum: 5", True),
         ("-1 -7 4", "min: -7\nmax: 4\nsum: -4", True)],
        ["split() turns a line of text into a list of words.",
         "Python has built-in functions for the smallest, largest, and total of a list."],
    ),
    challenge(
        "Sort by Length", "lists-and-tuples", "beginner",
        "Read words on one line, separated by spaces. Print them on one line, "
        "shortest first. Words of the same length keep their original order.",
        "words = input().split()\n# Print the words sorted by length",
        "words = input().split()\nprint(\" \".join(sorted(words, key=len)))",
        [("pear apple kiwi banana", "pear kiwi apple banana", False),
         ("ccc bb a", "a bb ccc", True), ("one", "one", True)],
        ["sorted() can take a key: a function used to compare the items.",
         "len is a function that measures each word.",
         "\" \".join() turns a list of words back into one line."],
    ),
    challenge(
        "Is It Sorted?", "lists-and-tuples", "beginner",
        "Read whole numbers on one line, separated by spaces. Print sorted if "
        "they are in ascending order (equal neighbours are fine), otherwise "
        "print not sorted.",
        "numbers = [int(n) for n in input().split()]\n# Print sorted or not sorted",
        "numbers = [int(n) for n in input().split()]\n"
        "print(\"sorted\" if numbers == sorted(numbers) else \"not sorted\")",
        [("1 3 6 8 9", "sorted", False), ("3 1", "not sorted", True),
         ("2 2 2", "sorted", True), ("5", "sorted", True)],
        ["A list is in order if sorting it would not change it.",
         "Two lists can be compared with ==."],
    ),
    challenge(
        "Class Report", "lists-and-tuples", "intermediate",
        "Read student averages on one line, separated by spaces. Print the "
        "minimum, maximum, and mean on one line with two decimals, like "
        "min=60.00 max=90.00 avg=78.33\n\nIf the line is empty, print no data instead.",
        "scores = [float(s) for s in input().split()]\n# Print the class statistics",
        "scores = [float(s) for s in input().split()]\nif not scores:\n    print(\"no data\")\n"
        "else:\n    average = sum(scores) / len(scores)\n"
        "    print(f\"min={min(scores):.2f} max={max(scores):.2f} avg={average:.2f}\")",
        [("85 90 60", "min=60.00 max=90.00 avg=78.33", False),
         ("72", "min=72.00 max=72.00 avg=72.00", True),
         ("\n", "no data", True), ("55 90 70.5", "min=55.00 max=90.00 avg=71.83", True)],
        ["An empty list is falsy, so if not scores: catches the empty case.",
         "The mean is the total divided by how many there are.",
         "Handle the empty case first, before dividing by the length."],
    ),

    # ------------------------------------------------------------------
    # Match Statements
    # ------------------------------------------------------------------
    challenge(
        "Weekend or Weekday", "match-statements", "beginner",
        "Read a day name in any capitals. Print weekend for Saturday or Sunday, "
        "weekday for Monday to Friday, and unknown for anything else. Use a "
        "match statement.",
        "day = input()\n# Use match to print weekend, weekday, or unknown",
        "day = input().strip().lower()\nmatch day:\n    case \"saturday\" | \"sunday\":\n"
        "        print(\"weekend\")\n"
        "    case \"monday\" | \"tuesday\" | \"wednesday\" | \"thursday\" | \"friday\":\n"
        "        print(\"weekday\")\n    case _:\n        print(\"unknown\")",
        [("Saturday", "weekend", False), ("friday", "weekday", True),
         ("SUNDAY", "weekend", True), ("funday", "unknown", True)],
        ["Make the input lower case before matching, so capitals do not matter.",
         "One case can match several values joined with |.",
         "case _: catches everything that matched nothing else."],
    ),
    challenge(
        "Point on an Axis", "match-statements", "intermediate",
        "Read an x coordinate and a y coordinate, one per line. Use match on the "
        "pair to print origin, on the y-axis, on the x-axis, or not on an axis.",
        "x = int(input())\ny = int(input())\n# Use match on (x, y)",
        "x = int(input())\ny = int(input())\nmatch (x, y):\n    case (0, 0):\n"
        "        print(\"origin\")\n    case (0, _):\n        print(\"on the y-axis\")\n"
        "    case (_, 0):\n        print(\"on the x-axis\")\n    case _:\n"
        "        print(\"not on an axis\")",
        [("0\n5", "on the y-axis", False), ("0\n0", "origin", True),
         ("3\n0", "on the x-axis", True), ("2\n-4", "not on an axis", True)],
        ["Put x and y together in a tuple and match on the tuple.",
         "Cases are checked in order, so put the origin first.",
         "_ inside a pattern matches any value."],
    ),
    challenge(
        "Status Codes", "match-statements", "beginner",
        "Read a web status code and print its meaning: 200 OK, 201 Created, "
        "404 Not Found, 500 Server Error, and Unknown for anything else.",
        "code = int(input())\n# Use match to print the meaning",
        "code = int(input())\nmatch code:\n    case 200:\n        print(\"OK\")\n"
        "    case 201:\n        print(\"Created\")\n    case 404:\n        print(\"Not Found\")\n"
        "    case 500:\n        print(\"Server Error\")\n    case _:\n        print(\"Unknown\")",
        [("404", "Not Found", False), ("200", "OK", True), ("201", "Created", True),
         ("500", "Server Error", True), ("302", "Unknown", True)],
        ["Each known code gets its own case.",
         "case _: handles every other code."],
    ),
    challenge(
        "Multiples of 3 and 5", "match-statements", "intermediate",
        "Read a whole number and print multiple of 3 and 5, multiple of 5, "
        "multiple of 3, or neither. Use match with guards.",
        "number = int(input())\n# Use match with guards",
        "number = int(input())\nmatch number:\n    case n if n % 15 == 0:\n"
        "        print(\"multiple of 3 and 5\")\n    case n if n % 5 == 0:\n"
        "        print(\"multiple of 5\")\n    case n if n % 3 == 0:\n"
        "        print(\"multiple of 3\")\n    case _:\n        print(\"neither\")",
        [("15", "multiple of 3 and 5", False), ("10", "multiple of 5", True),
         ("9", "multiple of 3", True), ("7", "neither", True), ("30", "multiple of 3 and 5", True)],
        ["A guard adds a condition to a case: case n if ...",
         "Order matters: check the case that covers both before the single ones.",
         "A number that is a multiple of both 3 and 5 is a multiple of 15."],
    ),
    challenge(
        "What Kind of Text?", "match-statements", "intermediate",
        "Read a line and print numeric if it is only digits, alphabetic if it is "
        "only letters, mixed if it is letters and digits, and other for anything "
        "else (such as spaces or symbols). Use match with guards.",
        "text = input()\n# Use match with guards and string methods",
        "text = input()\nmatch text:\n    case t if t.isnumeric():\n        print(\"numeric\")\n"
        "    case t if t.isalpha():\n        print(\"alphabetic\")\n"
        "    case t if t.isalnum():\n        print(\"mixed\")\n    case _:\n        print(\"other\")",
        [("32333", "numeric", False), ("Hello", "alphabetic", True),
         ("abc123", "mixed", True), ("hi there", "other", True), ("12.5", "other", True)],
        ["Strings have methods that answer True or False about their characters.",
         "isalnum() is True for letters, digits, or both, so check it last.",
         "A space or a dot is neither a letter nor a digit."],
    ),

    # ------------------------------------------------------------------
    # Sets and Dictionaries
    # ------------------------------------------------------------------
    challenge(
        "Unique Words", "sets-and-dictionaries", "beginner",
        "Read a sentence and print how many different words it contains. Capitals "
        "count, so Hello and hello are different words.",
        "sentence = input()\n# Print the number of different words",
        "sentence = input()\nprint(len(set(sentence.split())))",
        [("the cat and the hat", "4", False), ("a a a", "1", True), ("Hello hello", "2", True)],
        ["A set keeps only one copy of each value.",
         "split() gives you the words; len() counts them."],
    ),
    challenge(
        "Shared Students", "sets-and-dictionaries", "intermediate",
        "Read two lines, each listing student names separated by spaces. Print "
        "the names in both classes in alphabetical order on one line, or none "
        "if no one is in both.",
        "first = input().split()\nsecond = input().split()\n# Print the students in both classes",
        "first = set(input().split())\nsecond = set(input().split())\n"
        "shared = sorted(first & second)\nprint(\" \".join(shared) if shared else \"none\")",
        [("Alice Bob Charlie\nBob David", "Bob", False), ("Ann Bo\nCy Di", "none", True),
         ("Zed Amy Kim\nKim Amy", "Amy Kim", True)],
        ["Sets can find the values two groups have in common.",
         "The & operator or the intersection() method gives the shared names.",
         "sorted() puts them in alphabetical order."],
    ),
    challenge(
        "Word Frequency", "sets-and-dictionaries", "intermediate",
        "Read a sentence and print each different word with how many times it "
        "appears, one per line as word: count, in the order each word first "
        "appears.",
        "sentence = input()\n# Count each word with a dictionary",
        "counts = {}\nfor word in input().split():\n    counts[word] = counts.get(word, 0) + 1\n"
        "for word, count in counts.items():\n    print(f\"{word}: {count}\")",
        [("the cat the", "the: 2\ncat: 1", False), ("go", "go: 1", True),
         ("a b a b a", "a: 3\nb: 2", True)],
        ["A dictionary can map each word to its count.",
         "get(word, 0) gives the current count, or 0 for a new word.",
         "Dictionaries remember the order keys were first added."],
    ),

    # ------------------------------------------------------------------
    # Errors and Exceptions
    # ------------------------------------------------------------------
    challenge(
        "Safe Division", "errors-and-exceptions", "beginner",
        "Read two numbers, one per line. Print the first divided by the second "
        "with two decimals. If the second is zero, print Cannot divide by zero "
        "instead of crashing.",
        "a = float(input())\nb = float(input())\n# Divide safely",
        "a = float(input())\nb = float(input())\ntry:\n    print(f\"{a / b:.2f}\")\n"
        "except ZeroDivisionError:\n    print(\"Cannot divide by zero\")",
        [("10\n4", "2.50", False), ("5\n0", "Cannot divide by zero", True),
         ("-9\n3", "-3.00", True), ("0\n7", "0.00", True)],
        ["Dividing by zero raises an error called ZeroDivisionError.",
         "Put the division inside try: and handle that error in except."],
    ),
    challenge(
        "Numeric Salary", "errors-and-exceptions", "beginner",
        "Read a salary. If it is a whole number, print it. Otherwise print "
        "A numeric salary is required.",
        "text = input()\n# Convert safely with try and except",
        "text = input()\ntry:\n    print(int(text))\nexcept ValueError:\n"
        "    print(\"A numeric salary is required\")",
        [("52000", "52000", False), ("abc", "A numeric salary is required", True),
         ("12.5", "A numeric salary is required", True)],
        ["int() raises ValueError when the text is not a whole number.",
         "Try the conversion, and print the message in the except block."],
    ),
    challenge(
        "Playlist Pick", "errors-and-exceptions", "intermediate",
        "The playlist is Song A, Song B, and Song C. Read an index and print the "
        "song at that position. Negative indexes count from the end, as usual "
        "in Python. If the index is out of range or not a number, print Invalid index.",
        "songs = [\"Song A\", \"Song B\", \"Song C\"]\n# Read an index and print the song",
        "songs = [\"Song A\", \"Song B\", \"Song C\"]\ntry:\n    print(songs[int(input())])\n"
        "except (ValueError, IndexError):\n    print(\"Invalid index\")",
        [("1", "Song B", False), ("5", "Invalid index", True), ("-1", "Song C", True),
         ("two", "Invalid index", True)],
        ["Two different things can go wrong: the text is not a number, or the index is out of range.",
         "One except can catch several error types written as a tuple.",
         "Remember that indexes start at 0."],
    ),
]

# ----------------------------------------------------------------------
# From the midterm practice scenarios and the Week 3 practice list
# ----------------------------------------------------------------------
SEED_CHALLENGES += [
    challenge(
        "Vowel or Consonant", "strings", "beginner",
        "Read a single character. Print vowel if it is a, e, i, o, or u (in any "
        "case), consonant if it is any other letter, and not a letter otherwise.",
        "character = input()\n# Print vowel, consonant, or not a letter",
        "character = input().strip()\nif not character.isalpha():\n    print(\"not a letter\")\n"
        "elif character.lower() in \"aeiou\":\n    print(\"vowel\")\nelse:\n    print(\"consonant\")",
        [("a", "vowel", False), ("E", "vowel", True), ("z", "consonant", True),
         ("7", "not a letter", True)],
        ["Check that it is a letter first; isalpha() tells you.",
         "Lower-case the letter so you only need to check five vowels.",
         "in checks whether a character appears in a string."],
    ),
    challenge(
        "Alphabetical Order", "strings", "beginner",
        "Read two words, one per line. Print first comes before second, first "
        "comes after second, or same word, using the words themselves. Compare "
        "them the way Python does, where capital letters come before lower case.\n\n"
        "For example, apple and banana print apple comes before banana",
        "first = input()\nsecond = input()\n# Compare the words",
        "first = input()\nsecond = input()\nif first < second:\n"
        "    print(f\"{first} comes before {second}\")\nelif first > second:\n"
        "    print(f\"{first} comes after {second}\")\nelse:\n    print(\"same word\")",
        [("apple\nbanana", "apple comes before banana", False), ("cat\ncat", "same word", True),
         ("zebra\nant", "zebra comes after ant", True), ("Zoo\napple", "Zoo comes before apple", True)],
        ["Strings can be compared with < and >, just like numbers.",
         "Python compares strings letter by letter using each character's code.",
         "Every capital letter has a smaller code than every lower-case letter."],
    ),
    challenge(
        "Keyword Count", "strings", "beginner",
        "Read a keyword on the first line and survey responses on the second, "
        "separated by commas. Print how many responses contain the keyword, "
        "ignoring capitals.",
        "keyword = input()\nresponses = input().split(\",\")\n# Count the responses containing the keyword",
        "keyword = input().lower()\nresponses = input().split(\",\")\ncount = 0\n"
        "for response in responses:\n    if keyword in response.lower():\n        count += 1\nprint(count)",
        [("bad\nGreat staff,Bad service,Needs improvement,so BAD", "2", False),
         ("staff\nGreat staff,Rude staff", "2", True), ("zzz\nhello", "0", True)],
        ["split(\",\") breaks the line at each comma.",
         "Lower-case both the keyword and each response before comparing.",
         "in checks whether one string appears inside another."],
    ),
    challenge(
        "Wind Speed", "conditionals", "beginner",
        "Read a wind speed in km/h and print calm up to 10, breezy up to 20, "
        "windy up to 30, and stormy above 30.",
        "speed = int(input())\n# Print the wind category",
        "speed = int(input())\nif speed <= 10:\n    print(\"calm\")\nelif speed <= 20:\n"
        "    print(\"breezy\")\nelif speed <= 30:\n    print(\"windy\")\nelse:\n    print(\"stormy\")",
        [("15", "breezy", False), ("10", "calm", True), ("30", "windy", True), ("31", "stormy", True)],
        ["\"Up to 10\" includes 10, so use <=.",
         "Check the calmest category first and work upwards with elif."],
    ),
    challenge(
        "Free Shipping", "conditionals", "beginner",
        "Read a cart total on the first line and yes or no on the second (is the "
        "customer a member?). Members spending 150 or more get Free shipping. "
        "Members spending less see Spend 150 or more for free shipping. "
        "Non-members see Free shipping is for members only.",
        "total = float(input())\nmember = input()\n# Print the shipping message",
        "total = float(input())\nmember = input().strip().lower() == \"yes\"\nif not member:\n"
        "    print(\"Free shipping is for members only\")\nelif total >= 150:\n"
        "    print(\"Free shipping\")\nelse:\n    print(\"Spend 150 or more for free shipping\")",
        [("150\nyes", "Free shipping", False), ("149.99\nyes", "Spend 150 or more for free shipping", True),
         ("200\nno", "Free shipping is for members only", True),
         ("300\nYES", "Free shipping", True)],
        ["Lower-case the answer so YES and yes mean the same thing.",
         "Deal with non-members first; then only members are left.",
         "\"150 or more\" includes 150 itself."],
    ),
    challenge(
        "Comfort Level", "conditionals", "intermediate",
        "Read a temperature on the first line and a unit, C or F, on the second. "
        "In Celsius: hot from 20, comfortable from 10, otherwise cold. In "
        "Fahrenheit: hot from 90, comfortable from 50, otherwise cold. For any "
        "other unit, print invalid unit. Use nested if statements.",
        "temperature = int(input())\nunit = input()\n# Print hot, comfortable, cold, or invalid unit",
        "temperature = int(input())\nunit = input().strip().upper()\nif unit == \"C\":\n"
        "    if temperature >= 20:\n        print(\"hot\")\n    elif temperature >= 10:\n"
        "        print(\"comfortable\")\n    else:\n        print(\"cold\")\nelif unit == \"F\":\n"
        "    if temperature >= 90:\n        print(\"hot\")\n    elif temperature >= 50:\n"
        "        print(\"comfortable\")\n    else:\n        print(\"cold\")\nelse:\n"
        "    print(\"invalid unit\")",
        [("15\nC", "comfortable", False), ("20\nc", "hot", True), ("95\nF", "hot", True),
         ("40\nf", "cold", True), ("70\nK", "invalid unit", True)],
        ["Upper-case the unit so c and C mean the same thing.",
         "First decide the unit, then check the temperature inside each branch.",
         "Each unit has its own thresholds."],
    ),
    challenge(
        "Three Tries", "loops", "intermediate",
        "The valid usernames are ivan, james, and gill (any capitals). Read up to "
        "three usernames, one per line. Print Invalid username after each wrong "
        "one. Print Login successful and stop as soon as one is valid. After "
        "three wrong attempts, print Access denied.",
        "valid_usernames = [\"ivan\", \"james\", \"gill\"]\n# Allow up to three attempts",
        "valid_usernames = [\"ivan\", \"james\", \"gill\"]\nfor attempt in range(3):\n"
        "    if input().strip().lower() in valid_usernames:\n        print(\"Login successful\")\n"
        "        break\n    print(\"Invalid username\")\nelse:\n    print(\"Access denied\")",
        [("bob\nIVAN", "Invalid username\nLogin successful", False), ("gill", "Login successful", True),
         ("a\nb\nc", "Invalid username\nInvalid username\nInvalid username\nAccess denied", True),
         ("x\ny\njames", "Invalid username\nInvalid username\nLogin successful", True)],
        ["A loop that runs at most three times fits range(3).",
         "break leaves the loop early as soon as the login succeeds.",
         "A for loop can have an else block that runs only if the loop never hit break."],
    ),
    challenge(
        "Temperature Report", "lists-and-tuples", "intermediate",
        "Read temperatures on one line, separated by spaces. Print each one's "
        "category on its own line: cold up to 15, warm up to 25, hot above 25. "
        "Then print Most frequent: followed by the most common category. If "
        "categories tie, use the one that appeared first.",
        "temperatures = [int(t) for t in input().split()]\n# Print each category, then the most frequent",
        "temperatures = [int(t) for t in input().split()]\ncategories = []\n"
        "for temperature in temperatures:\n    if temperature <= 15:\n        category = \"cold\"\n"
        "    elif temperature <= 25:\n        category = \"warm\"\n    else:\n        category = \"hot\"\n"
        "    print(category)\n    categories.append(category)\n"
        "print(f\"Most frequent: {max(categories, key=categories.count)}\")",
        [("23 2 11 60", "warm\ncold\ncold\nhot\nMost frequent: cold", False),
         ("5 15 26 60", "cold\ncold\nhot\nhot\nMost frequent: cold", True),
         ("30", "hot\nMost frequent: hot", True), ("20 30", "warm\nhot\nMost frequent: warm", True)],
        ["Build a list of categories as you go.",
         "list.count(value) tells you how often a value appears.",
         "max() can take a key; with key=categories.count it picks the most common."],
    ),
    challenge(
        "Menu Order", "match-statements", "beginner",
        "The menu is 1 fries ($8.99), 2 pizza ($10.99), and 3 salad ($20.99). "
        "Read an option number and print the item and its price like "
        "pizza: $10.99, or Invalid option. Use a match statement.",
        "choice = int(input())\n# Use match to print the item and price",
        "choice = int(input())\nmatch choice:\n    case 1:\n        print(\"fries: $8.99\")\n"
        "    case 2:\n        print(\"pizza: $10.99\")\n    case 3:\n        print(\"salad: $20.99\")\n"
        "    case _:\n        print(\"Invalid option\")",
        [("2", "pizza: $10.99", False), ("1", "fries: $8.99", True), ("3", "salad: $20.99", True),
         ("4", "Invalid option", True), ("0", "Invalid option", True)],
        ["Each menu number gets its own case.",
         "case _: handles every number that is not on the menu."],
    ),
    challenge(
        "Class Results", "match-statements", "intermediate",
        "Read student names on the first line and their grades on the second, "
        "both separated by spaces. Print each student as Name: Pass (50 or more) "
        "or Name: Fail. Then print Average: with two decimals, and finally "
        "Excellent (80 or more), Good (60 or more), Needs improvement (50 or "
        "more), or Failing. Use a match statement for the final message.",
        "names = input().split()\ngrades = [int(g) for g in input().split()]\n# Print the results",
        "names = input().split()\ngrades = [int(g) for g in input().split()]\n"
        "for name, grade in zip(names, grades):\n"
        "    print(f\"{name}: {'Pass' if grade >= 50 else 'Fail'}\")\n"
        "average = sum(grades) / len(grades)\nprint(f\"Average: {average:.2f}\")\n"
        "match average:\n    case a if a >= 80:\n        print(\"Excellent\")\n"
        "    case a if a >= 60:\n        print(\"Good\")\n    case a if a >= 50:\n"
        "        print(\"Needs improvement\")\n    case _:\n        print(\"Failing\")",
        [("Ivan James Lisa Tina\n90 50 30 95",
          "Ivan: Pass\nJames: Pass\nLisa: Fail\nTina: Pass\nAverage: 66.25\nGood", False),
         ("Ann\n100", "Ann: Pass\nAverage: 100.00\nExcellent", True),
         ("Bo Cy\n40 45", "Bo: Fail\nCy: Fail\nAverage: 42.50\nFailing", True),
         ("Di Ed\n50 50", "Di: Pass\nEd: Pass\nAverage: 50.00\nNeeds improvement", True)],
        ["zip() pairs each name with its grade.",
         "The average is the total divided by how many grades there are.",
         "Guards in match (case a if a >= 80) are checked in order, highest first."],
    ),
]