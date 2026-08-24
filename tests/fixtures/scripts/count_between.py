"""Append label between to the suite invocation log (integration fixture)."""

LABEL = "between"


def main() -> None:
    from colosseum.context import get_context

    out = get_context().output_dir
    assert out is not None
    path = out / "invocations.txt"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{LABEL}\n")
