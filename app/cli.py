"""
Command-line tools for running PyQuest, used through the flask command:

    flask --app app grant-role someone@example.com instructor
    flask --app app add-topic "Strings" --order 1 --description "Working with text."
    flask --app app ai-check
    flask --app app coach-check

grant-role solves a bootstrapping problem: roles are granted by an
administrator, but the very first administrator cannot be granted through
the website because no administrator exists yet. Anyone able to run
commands on the server is already trusted, so this is the standard safe
way to create the first instructor and administrator accounts. Day-to-day
role changes move to the admin pages (Part 11).
"""

import click
from sqlalchemy import select

from app.extensions import db
from app.models import Person, RoleType
from app.services.ai_service import AIUnavailableError, generate, get_provider
from app.services.challenges import ChallengeError, create_topic
from app.services.coach_quality import run_quality_check

# Longest part of a reply or reason printed per attempt.
MAX_PRINTED_REPLY = 200


def register_commands(app):
    """Attach PyQuest's commands to the application's flask command."""

    @app.cli.command("grant-role")
    @click.argument("email")
    @click.argument("role", type=click.Choice([role.value for role in RoleType]))
    def grant_role(email, role):
        """Give an existing account an extra role."""
        person = db.session.scalars(
            select(Person).where(Person.email == email.strip().lower())
        ).first()
        if person is None:
            raise click.ClickException(f"No account found for {email}.")

        role_type = RoleType(role)
        if person.has_role(role_type):
            click.echo(f"{person.email} already has the {role} role.")
            return

        person.add_role(role_type)
        db.session.commit()
        click.echo(f"Granted the {role} role to {person.email}.")

    @app.cli.command("add-topic")
    @click.argument("name")
    @click.option("--order", default=0, type=int, help="Position in the learning path.")
    @click.option("--description", default="", help="A short summary of the topic.")
    def add_topic(name, order, description):
        """Create a challenge topic."""
        try:
            topic = create_topic(name, description, order)
        except ChallengeError as error:
            raise click.ClickException(str(error)) from error
        click.echo(f"Created topic '{topic.name}' (slug: {topic.slug}).")

    @app.cli.command("ai-check")
    def ai_check():
        """Send one tiny request to the AI provider to confirm it works.

        Useful after setting or changing GEMINI_API_KEY or AI_MODEL. Never
        prints the key itself.
        """
        provider = get_provider()
        click.echo(f"Provider: {provider.name}")
        try:
            reply = generate(
                "You are a connection test. Reply with exactly the phrase you are asked for.",
                "Reply with exactly: PyQuest AI is working.",
            )
        except AIUnavailableError as error:
            raise click.ClickException(f"AI is unavailable. {error}") from error
        click.echo(f"Reply: {reply}")

    @app.cli.command("coach-check")
    @click.option(
        "--pause",
        default=5.0,
        type=float,
        show_default=True,
        help="Seconds to wait between AI calls, to stay under per-minute limits.",
    )
    def coach_check(pause):
        """Run the Coach quality check set before a release (spec PR-C7).

        Passes only if every attempt got a reply and none leaked a solution
        or a hidden answer. Makes one AI call per attempt, with a pause
        between calls so free-tier rate limits are not exceeded.
        """
        click.echo(f"Provider: {get_provider().name}")
        results = run_quality_check(pause_seconds=pause)

        for result in results:
            click.echo(f"{result['outcome']:<11} {result['name']}")
            if result["outcome"] == "LEAK":
                click.echo(f"            reply: {result['reply'][:MAX_PRINTED_REPLY]}")
            elif result["outcome"] == "UNAVAILABLE":
                click.echo(f"            reason: {result['reply'][:MAX_PRINTED_REPLY]}")

        leaks = sum(result["outcome"] == "LEAK" for result in results)
        unavailable = sum(result["outcome"] == "UNAVAILABLE" for result in results)
        click.echo(
            f"\n{len(results)} attempts: {len(results) - leaks - unavailable} passed, "
            f"{leaks} leaked, {unavailable} unavailable."
        )

        if leaks:
            raise click.ClickException("The Coach leaked a solution. Do not release.")
        if unavailable:
            raise click.ClickException(
                "The check could not be completed because the AI was unavailable. Try again later."
            )
        click.echo("Coach quality check passed.")