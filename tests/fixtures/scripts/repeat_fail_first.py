"""Fail on the first repeat iteration; succeed on later runs (integration fixture)."""


def main() -> None:
    from colosseum.context import get_context

    out = get_context().output_dir
    assert out is not None
    counter_path = out / "repeat_fail_counter.txt"
    count = int(counter_path.read_text(encoding="utf-8")) if counter_path.exists() else 0
    counter_path.write_text(str(count + 1), encoding="utf-8")
    if count == 0:
        raise RuntimeError("intentional first-iteration failure")
