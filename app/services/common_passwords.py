"""
Passwords too common to allow (spec FR01).

Attackers try the most common passwords first, so a password on this list
offers little protection even if it meets the length rule. Only passwords
at least 10 characters long are listed, because anything shorter is already
rejected by the minimum length.

This is a short built-in list suited to R1. A larger published list (tens
of thousands of entries) can replace it later without changing any other
code, since callers only use is_common_password().
"""

COMMON_PASSWORDS = frozenset({
    "0000000000", "0123456789", "1111111111", "1234567890", "12345678910",
    "123456789a", "1234567890a", "9876543210", "1q2w3e4r5t", "1q2w3e4r5t6y",
    "q1w2e3r4t5", "qwertyuiop", "qwertyuiop1", "qwerty1234", "qwerty12345",
    "qwerty123456", "asdfghjkl1", "asdfghjkl;", "zxcvbnm123", "qazwsxedcr",
    "zaq12wsxcde", "aaaaaaaaaa", "abcdefghij", "abc1234567", "abcdef123456",
    "password12", "password123", "password1234", "password12345",
    "passw0rd123", "mypassword", "mypassword1", "changeme123", "letmein123",
    "letmeinnow", "welcome123", "welcome1234", "trustno1234", "iloveyou12",
    "iloveyou123", "iloveyou1234", "princess123", "sunshine123",
    "football123", "baseball123", "superman123", "starwars123", "monkey12345",
    "dragon12345", "michael123", "jennifer123", "charlie123", "computer123",
    "internet123", "administrator", "adminadmin", "admin12345",
    "pythonpython", "python12345", "pyquest123", "pyquest1234",
})


def is_common_password(password):
    """Return True if the password is on the common-password list.

    The comparison ignores capitals, because "Password123" is guessed just
    as easily as "password123".
    """
    return password.lower() in COMMON_PASSWORDS