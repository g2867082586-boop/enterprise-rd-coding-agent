from pathlib import Path


class UnsafeCommandError(ValueError):
    pass


ALLOWED_COMMANDS = {"pytest", "ruff"}
FORBIDDEN_TOKENS = {"&&", "||", "|", ">", "<", ";", "`", "$(", "${"}
FORBIDDEN_OPTIONS = {
    "--basetemp", "--confcutdir", "--override-ini", "--rootdir", "--trace-config",
    "--fix", "--unsafe-fixes", "-p",
}


def _validate_path_argument(argument: str, project_root: Path) -> None:
    """Reject path-like arguments that resolve outside the project workspace."""
    if not any(token in argument for token in ("/", "\\")) and not argument.startswith("."):
        return
    candidate = Path(argument)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    try:
        candidate.resolve().relative_to(project_root.resolve())
    except ValueError as exc:
        raise UnsafeCommandError("path argument escapes project root") from exc


def validate_command(command: str, args: list[str], project_root: Path) -> tuple[str, list[str]]:
    if command not in ALLOWED_COMMANDS:
        raise UnsafeCommandError(f"command is not allowlisted: {command}")
    for arg in args:
        if "\x00" in arg:
            raise UnsafeCommandError("null bytes are forbidden")
        if any(token in arg for token in FORBIDDEN_TOKENS):
            raise UnsafeCommandError("shell control tokens are forbidden")
        option = arg.split("=", 1)[0]
        if option in FORBIDDEN_OPTIONS:
            raise UnsafeCommandError(f"unsafe command option is forbidden: {option}")
        _validate_path_argument(arg, project_root)
    return command, args
