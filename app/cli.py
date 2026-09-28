"""
Command-line tools for running PyQuest, used through the flask command:

    flask --app app grant-role someone@example.com instructor
    flask --app app add-topic "Strings" --order 1 --description "Working with text."
    flask --app app ai-check

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