"""
Created on Sat Jan 14 18:03 2023 (UTC)

This is the interface that allows Wikiportret to operate through a graphical interface

@author: Daniuu
"""
import tkinter
import Wikiportret_core as core
import Wikiportret_GUI_aux_functions as aux
import Wikiportret_GUI_text_NL as nlt

root = tkinter.Tk()
root.title('Wikiportret GUI')
root.state('zoomed')  # Open the application in full-screen

root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)

window_width, window_height = root.winfo_screenwidth(), root.winfo_screenheight()

#Define some properties of the font
font = (aux.default_font, 14)
input_font = (aux.default_font, 16)


root.mainloop()