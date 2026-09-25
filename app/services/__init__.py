"""
Service layer: PyQuest's business rules.

Services are plain Python functions with no knowledge of web requests,
forms, or templates. Views (routes) collect input, call a service, and turn
the result into a response. Keeping the rules here means they can be tested
directly, reused by any future interface (an API, a command-line tool), and
changed without touching web code (spec section 9: "routes stay thin").
"""