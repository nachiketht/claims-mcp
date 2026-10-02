import logging
import sys

from agent import run


def main(argv: list[str] | None = None) -> int:
    chosen = sys.argv[1:] if argv is None else argv
    sentence = " ".join(chosen).strip()
    if not sentence:
        print('usage: python ask.py "E1002 needs a monitor."')
        return 2
    claim_log = logging.getLogger("claims")
    claim_log.setLevel(logging.INFO)
    claim_log.propagate = False
    claim_log.handlers.clear()
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(message)s"))
    claim_log.addHandler(stream)
    try:
        for _event in run(sentence):
            pass
    except RuntimeError as error:
        print(error)
        return 1
    finally:
        for handler in claim_log.handlers:
            handler.close()
        claim_log.handlers.clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
