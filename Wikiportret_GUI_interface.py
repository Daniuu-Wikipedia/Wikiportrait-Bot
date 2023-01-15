"""
Created on Sat Jan 14 18:03 2023 (UTC)

This is the interface that allows Wikiportret to operate through a graphical interface

@author: Daniuu
"""
import tkinter
import Wikiportret_core as Core
import Wikiportret_GUI_aux_functions as Aux
import Wikiportret_GUI_text_NL as Nlt

root = tkinter.Tk()
root.title('Wikiportret GUI')
# root.state('zoomed')  # Open the application in full-screen

ncol, nrow = 14, 16
for i in range(ncol):
    root.columnconfigure(i, weight=1)
for i in range(nrow):
    root.rowconfigure(i, weight=1)

# Set variables for window_width & window_height (use 10 px padding)
window_width, window_height = root.winfo_screenwidth() - 10, root.winfo_screenheight() - 10
col_width, col_height = int(window_width//ncol), int(window_height//nrow)

# Define some properties of the font
font = (Aux.default_font, 14)
# Write the widgets that read the input
# Text widgets
image_text = tkinter.Label(root, text='Afbeelding:', font=font)
image_text.grid(row=0, column=0, columnspan=1, sticky='NW')
article_text = tkinter.Label(root, text='Artikel:', font=font)
article_text.grid(row=0, column=7, columnspan=1, sticky='NE')
# Widgets that effectively read the input
image = tkinter.StringVar()  # The variable that contains the name of the processed image
image_input = tkinter.Entry(root, font=font, textvariable=image)
article = tkinter.StringVar()  # Variable to store the name of the target article
article_input = tkinter.Entry(root, font=font, textvariable=article)
image_input.grid(row=0, column=1, columnspan=6, sticky="NEW", padx=2)
article_input.grid(row=0, column=8, columnspan=6, sticky="NEW", padx=2)

# Write the labels to divide the workspace into three
root.mainloop()
