"""Console script for daylight_timelapser."""
import sys
import click


@click.command()
def main(args=None):
    """Console script for daylight_timelapser."""
    click.echo("Replace this message by putting your code into "
               "daylight_timelapser.cli.main")
    click.echo("See click documentation at https://click.palletsprojects.com/")
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
