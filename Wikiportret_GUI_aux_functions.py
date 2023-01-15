"""
Created by Daniuu

This file contains a variety of auxiliary functions (to be used with the GUI-code)
"""

import tkinter
from tkinter.constants import DISABLED, NORMAL
from Wikiportret_GUI_text_NL import manual_text, execute_text


# Define a function to generate buttons to switch a command's execution on/off
class ExecutionBox:
    def __init__(self, window: (tkinter.Frame, tkinter.Tk), fields: tuple = ()) -> None:
        self._var = tkinter.IntVar()
        self._fields = fields
        self._box = tkinter.Checkbutton(window, text=execute_text, onvalue=1, offvalue=0, variable=self._var)

    def manipulate_fields(self) -> None:
        if self.active:
            return self.activate()
        return self.deactivate()

    def deactivate(self) -> None:
        for i in self._fields:
            i['state'] = DISABLED
            if isinstance(i, ManualBox):  # Make sure to also deactivate the widgets controlled by this box
                i.deactivate()

    def activate(self) -> None:
        for i in self._fields:
            i['state'] = NORMAL
            if isinstance(i, ManualBox):
                i.activate()

    def value(self) -> int:
        return self._var.get()

    def uncheck(self) -> None:
        self._var.set(0)
        self.deactivate()

    @property
    def active(self) -> bool:
        return self._var.get() == 1


class ManualBox:
    manual_color_off = r'#800000'  # The color of the text if the checkbox is off
    manual_color_on = r'#ff0000'  # The color of the text if the checkbox is checked (and a manual override is active)

    def __init__(self, window: (tkinter.Frame, tkinter.Tk), fields: tuple = ()) -> None:
        self._var, self._fields = tkinter.IntVar(), fields
        self._box = tkinter.Checkbutton(window, text=manual_text, onvalue=1, offvalue=0, variable=self._var)

    def deactivate(self) -> None:
        # Deactivates the checkbox and all other buttons that it controls
        self._box['state'] = DISABLED
        self.deactivate_buttons()

    def activate(self) -> None:
        # Activates the checkbox itself (and the buttons it controls if switched on)
        self._box['state'] = NORMAL
        self.activate_buttons()

    def activate_buttons(self) -> None:
        if self.active:
            for i in self._fields:
                i['state'] = NORMAL

    def deactivate_buttons(self) -> None:
        for i in self._fields:
            i['state'] = DISABLED

    def uncheck(self) -> None:
        self._var.set(0)
        for i in self._fields:
            i['state'] = DISABLED

    def value(self) -> int:
        return self._var.get()

    @property
    def active(self) -> bool:
        return self._var.get() == 1


def make_frame(root: tkinter.Tk,
               rel_width: float,
               rel_height: float,
               rows: int = 1,
               cols: int = 1,
               row_weight: dict = None,
               col_weight: dict = None) -> tkinter.Frame:
    assert 0 < rel_width <= 1, 'The passed relative width of the frame must be a number between 0 and 1!'
    assert 0 < rel_height <= 1, 'The passed relative height of the frame must be a number between 0 and 1!'
    frame = tkinter.Frame(root,
                          width=rel_width * root.winfo_screenwidth(),
                          height=rel_height * root.winfo_screenheight())
    if row_weight is not None:
        for i in range(rows):
            frame.rowconfigure(i, weight=row_weight.get(i, 1))
    if col_weight is not None:
        for i in range(cols):
            frame.columnconfigure(i, weight=col_weight.get(i, 1))
    return frame


# Some handy built-in functions
cv = tkinter.N + tkinter.S
ch = tkinter.E + tkinter.W

center = cv + ch

default_font = 'Arial'