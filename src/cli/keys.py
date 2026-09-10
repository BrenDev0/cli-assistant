from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.key_binding import KeyBindings

from src.core import mode
from src.core.lang import t

from . import ui


def bindings() -> KeyBindings:
    keys = KeyBindings()

    # bound on the approval prompt too, so the answer to "do I have to keep saying yes"
    # is reachable from the question itself
    @keys.add("s-tab")
    def _(event) -> None:
        on = mode.toggle_auto()
        # run_in_terminal rather than printing straight from the handler, which would
        # write into the line prompt_toolkit is drawing
        run_in_terminal(lambda: ui.notice(t("auto.on" if on else "auto.off")))
        event.app.invalidate()

    return keys
