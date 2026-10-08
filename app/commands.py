import click
from flask.cli import with_appcontext

from app.errors import ErrorAPI
from app.extensions import db
from app.models import Usuario


@click.command("set-password")
@click.argument("usuario_id", type=click.IntRange(min=1))
@click.password_option(confirmation_prompt=True)
@with_appcontext
def set_password(usuario_id, password):
    """Asignar contraseña a una cuenta existente desde un terminal de confianza."""
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        raise click.ClickException("Usuario no encontrado.")
    try:
        usuario.set_password(password)
        db.session.commit()
    except ErrorAPI as error:
        db.session.rollback()
        raise click.ClickException(error.mensaje)
    click.echo("Contraseña actualizada; los tokens anteriores quedan invalidados.")
