"""
Created on Sat Jan 14 18:03 2023 (UTC)

This is the interface that allows Wikiportret to operate through a graphical interface

@author: Daniuu
"""
import tkinter
import Wikiportret_core as core
import Wikiportret_GUI_aux_functions as aux
import Wikiportret_GUI_text_NL as text

root = tkinter.Tk()
root.title('Wikiportret GUI')

# Create the frames for the input section
input_frame = aux.make_frame(root, 1, 0.1)
input_frame.grid(column=0, row=0, columnspan=3, sticky=tkinter.N + aux.ch)

root.mainloop()