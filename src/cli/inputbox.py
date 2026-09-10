import asyncio

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.key_binding.defaults import load_key_bindings
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import BufferControl, FormattedTextControl, Layout, Window
from prompt_toolkit.layout.containers import ConditionalContainer, HSplit, VSplit

from . import ui


class InputBox:
    """The line you type on, held at the bottom of the terminal inside a border whose
    bottom edge carries the model and the modes.

    A PromptSession cannot be made to do this. Its input renders wherever the cursor
    happens to be, while a bottom_toolbar is pinned to the last row of the terminal, so
    on anything but a full screen the two end up separated by every unused row between
    them. Anchoring both means owning the layout: the empty window above the border
    takes all the slack, which pushes the box onto the last rows however tall the
    region turns out to be.

    The application runs for the whole session rather than once per turn. Enter hands
    the line over through a queue and clears the buffer, so the box stays on screen
    while the turn is worked on -- starting and stopping it per turn left the bottom of
    the terminal empty for as long as the model took to answer. Everything printed
    meanwhile goes above it, which is what patch_stdout is for.
    """

    def __init__(self, left, status, tasks=None, extra_bindings=None,
                 input=None, output=None):
        self._left = left
        self._status = status
        self._tasks = tasks or dict
        self._lines: asyncio.Queue[str | None] = asyncio.Queue()
        self._buffer = Buffer(multiline=False, history=InMemoryHistory())
        self._app = self._build(extra_bindings, input, output)
        self._task: asyncio.Task | None = None

    async def __aenter__(self) -> "InputBox":
        self._task = asyncio.create_task(self._app.run_async())
        return self

    async def __aexit__(self, *_) -> None:
        # is_done, not just is_running: ctrl-c exits the application from inside its own
        # key handler, and it is still running while it unwinds. A second exit() there
        # raises over the return value the first one set.
        if self._app.is_running and not self._app.is_done:
            self._app.exit()

        if self._task:
            await asyncio.gather(self._task, return_exceptions=True)

    async def next(self) -> str | None:
        """The next submitted line, or None once the user has asked to leave."""
        return await self._lines.get()

    def _build(self, extra, input, output) -> Application:
        keys = KeyBindings()

        @keys.add("enter")
        def _submit(event) -> None:
            text = self._buffer.text
            self._buffer.reset()
            self._lines.put_nowait(text)

        @keys.add("c-c")
        @keys.add("c-d")
        def _quit(event) -> None:
            self._lines.put_nowait(None)
            event.app.exit()

        # the defaults first, for ordinary editing and history, then ours on top: the
        # basic bindings treat enter as inserting a newline, which a one-line input
        # must not do
        bindings = [load_key_bindings()]
        if extra:
            bindings.append(extra)
        bindings.append(keys)

        # the trailing single-column window is the gap the borders leave at the right,
        # so the edge below lines up with the corners above instead of sitting a column
        # further out
        row = VSplit([
            Window(FormattedTextControl(lambda: self._left()), width=ui.LEFT_WIDTH),
            Window(BufferControl(self._buffer), wrap_lines=False),
            Window(FormattedTextControl(ui.input_right), width=1),
            Window(width=1),
        ], height=1)

        # its own box above the input, and gone entirely when nothing is running:
        # dont_extend_height so it takes exactly the rows its content needs, leaving
        # the filler above to keep pushing everything onto the last lines
        panel = ConditionalContainer(
            Window(
                FormattedTextControl(lambda: ui.tasks_panel(self._tasks())),
                dont_extend_height=True,
            ),
            filter=Condition(lambda: bool(self._tasks())),
        )

        return Application(
            layout=Layout(HSplit([
                Window(),
                panel,
                Window(FormattedTextControl(ui.top_edge), height=1),
                row,
                Window(FormattedTextControl(lambda: self._status()), height=1),
            ])),
            key_bindings=merge_key_bindings(bindings),
            input=input,
            output=output,
            full_screen=False,
            # redraws on its own so the modes and the running-task list stay current
            # while a turn is being worked on
            refresh_interval=0.5,
            erase_when_done=True,
        )
