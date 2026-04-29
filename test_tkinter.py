import tkinter as tk

root = tk.Tk()
root.title("Test Tkinter Window")
label = tk.Label(root, text="If you see this, tkinter is working!")
label.pack(padx=40, pady=40)
root.mainloop()
