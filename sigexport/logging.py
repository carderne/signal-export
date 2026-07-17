from typer import colors, secho

verbose: bool = False


def log(msg: str, fg: str = colors.BLACK) -> None:
    if verbose:
        secho(msg, fg=fg)
