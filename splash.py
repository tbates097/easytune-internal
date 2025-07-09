import tkinter as tk
from tkinter import ttk
import time
import threading
import sys

def show_splash():
    splash = tk.Tk()
    splash.title("Loading...")
    splash.geometry("300x100")
    splash.configure(bg="#F0F0F0")

    label = tk.Label(splash, text="Starting the application...", bg="#F0F0F0", font=("Segoe UI", 12))
    label.pack(pady=10)

    progress = ttk.Progressbar(splash, orient="horizontal", length=200, mode="indeterminate")
    progress.pack(pady=10)
    progress.start()

    def close_splash():
        time.sleep(5)  # Simulate loading time
        splash.quit()  # Use quit to exit the main loop

    threading.Thread(target=close_splash).start()
    splash.mainloop()

if __name__ == "__main__":
    show_splash()
    sys.exit()  # Ensure the script exits cleanly after the main loop