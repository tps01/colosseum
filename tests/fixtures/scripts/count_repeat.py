"""Append label test to the suite invocation log (repeat fixture)."""

LABEL = "test"


def main() -> None:
    from colosseum.context import get_context

    out = get_context().output_dir
    assert out is not None
    path = out / "invocations.txt"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{LABEL}\n")
