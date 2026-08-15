import tkinter as tk
from tkinter import messagebox
def saludar():
    n=0
    messagebox.showinfo("saludo", "hola gamers")
ventana = tk.Tk()
ventana.geometry("300x200")
ventana.title("mi primer app")
etiqueta=tk.Label(ventana,text="hola gamers")
etiqueta.pack()
boton=tk.Button(ventana,text="holaaaa", command=saludar)
boton.pack()
ventana.mainloop()