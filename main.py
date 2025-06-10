import os
import threading
import tkinter as tk
from tkinter import messagebox
from ftplib import FTP
import time
from datetime import datetime
import shutil
from PIL import Image, ImageTk


# === CONFIG ===
FTP_HOST = "affiliati.diperspesa.it"
FTP_USER = "GCAFF103"
FTP_PASS = "$af103user"
FTP_BASE_DIR = "/Gescom/ftpaffiliati/00103"
FTP_FATTURE_DIR = f"{FTP_BASE_DIR}/fatture"
FILE_LIST = ["ANAINT", "BARCODE", "ARTBIL", "VPREZZI", "PROMO"]
LOCAL_IMPORT_DIR = r"\\192.168.1.197\store\USER\IMPORT"
SAVE_DIR = os.path.join(LOCAL_IMPORT_DIR, "SAVE")
SESSIONE_PATH = os.path.join(LOCAL_IMPORT_DIR, "sessione.txt")
DOCFOR_PATH = os.path.join(LOCAL_IMPORT_DIR, "DOCFOR")

# === STATO ===
terminate_import = False  # flag di terminazione

# === GUI Setup (tema scuro) ===
BG_COLOR = "#1e1e1e"
FG_COLOR = "#ffffff"
BTN_COLOR = "#333333"
HIGHLIGHT = "#555555"

root = tk.Tk()
root.title("Importazione File")
root.configure(bg=BG_COLOR)
root.resizable(False, False)
window_width = 480
window_height = 480

# === Centro schermo e in primo piano ===
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
position_top = int(screen_height / 2 - window_height / 2)
position_left = int(screen_width / 2 - window_width / 2)
root.geometry(f"{window_width}x{window_height}+{position_left}+{position_top}")
root.attributes('-topmost', True)

label_status = tk.Label(root, text="Importazione file su STORE", font=("Arial", 14),
                        bg=BG_COLOR, fg=FG_COLOR)
label_status.pack(pady=10)

#rotella_label = tk.Label(root, text="", font=("Arial", 20), bg=BG_COLOR, fg=FG_COLOR)
#rotella_label.pack()

info_label = tk.Label(
    root,
    text="PDV: 00103  ROSITANO",
    font=("Arial", 11),
    bg="#3a3a3a",
    fg="#ffffff",
    anchor="w",      # allinea a sinistra
    padx=10,         # margine interno sinistro
    pady=4
)
info_label.pack(fill='x', pady=(5, 0))  

listbox_frame = tk.Frame(root, bg=BG_COLOR)
listbox_frame.pack(pady=10)

scrollbar = tk.Scrollbar(listbox_frame)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

file_listbox = tk.Listbox(listbox_frame, width=55, height=10,
                          bg=BG_COLOR, fg=FG_COLOR, highlightbackground=HIGHLIGHT,
                          selectbackground="#444", yscrollcommand=scrollbar.set)
file_listbox.pack(side=tk.LEFT)
scrollbar.config(command=file_listbox.yview)

progress_label = tk.Label(root, text="", font=("Arial", 10), bg=BG_COLOR, fg=FG_COLOR)
progress_label.pack()

#spinner_running = False
#spinner_index = 0
#spinner_frames = ['⌛', '⏳', '🔄', '🕒']


#def animate_spinner():
#    global spinner_index
#    if spinner_running and not terminate_import:
#        rotella_label.config(text=spinner_frames[spinner_index % len(spinner_frames)])
#        spinner_index += 1
#        root.after(300, animate_spinner)
#    else:
#        rotella_label.config(text="")


def salva_copia(nome_file):
    if terminate_import:
        return
    os.makedirs(SAVE_DIR, exist_ok=True)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    src = os.path.join(LOCAL_IMPORT_DIR, nome_file)
    dst = os.path.join(SAVE_DIR, f"{now}_{nome_file}")
    if os.path.exists(src):
        shutil.copy2(src, dst)


def safe_insert(text):
    if not terminate_import:
        root.after(0, lambda: (
            file_listbox.insert(tk.END, text),
            file_listbox.yview_moveto(1)
        ))


def safe_progress(text):
    if not terminate_import:
        root.after(0, lambda: progress_label.config(text=text))

def pulisci_file_finale(path_file):
    if not os.path.exists(path_file):
        return
    with open(path_file, "rb") as f:
        content = f.read()
    original_length = len(content)
    while content and content[-1] in (0x1C, 0x1A):
        content = content[:-1]
    if len(content) < original_length:
        print(f"[DEBUG] Rimossi {original_length - len(content)} byte finali da {os.path.basename(path_file)}")
    with open(path_file, "wb") as f:
        f.write(content)

def run_import():
    loading_frame = tk.Frame(root, bg=BG_COLOR)
    dot_labels = [
        tk.Label(loading_frame, text="●", font=("Arial", 14), fg=FG_COLOR, bg=BG_COLOR),
        tk.Label(loading_frame, text="●", font=("Arial", 14), fg=FG_COLOR, bg=BG_COLOR),
        tk.Label(loading_frame, text="●", font=("Arial", 14), fg=FG_COLOR, bg=BG_COLOR)
    ]
    for lbl in dot_labels:
        lbl.pack()

    try:
        if os.path.exists("logo.png"):
            img = Image.open("logo.png")
            ...
        else:
            print("logo.png non trovato")
        img = img.resize((50, 50))
        tk_img = ImageTk.PhotoImage(img)

        image_label = tk.Label(loading_frame, image=tk_img, bg=BG_COLOR)
        image_label.image = tk_img
        image_label.pack(pady=(5, 5))
    except Exception as e:
        print(f"Errore caricamento immagine: {e}")

    def animate_dots(index=0):
        if not spinner_running or terminate_import:
            loading_frame.pack_forget()
            return
        for i, lbl in enumerate(dot_labels):
            lbl.config(fg="#ffffff" if i == index else "#555555")
        root.after(300, lambda: animate_dots((index + 1) % 3))


    def task():
        global spinner_running
        root.after(0, lambda: btn_download.pack_forget())
        root.after(0, lambda: loading_frame.pack(pady=5))
        root.after(0, lambda: animate_dots())

        try:
            spinner_running = True
            #animate_spinner()

            safe_progress("Connessione all'FTP...")
            try:
                ftp = FTP(FTP_HOST)
                ftp.login(FTP_USER, FTP_PASS)
            except Exception as e:
                spinner_running = False
                safe_progress("Errore di connessione FTP")
                error_msg = f"Impossibile connettersi all'FTP:\n{e}"
                root.after(0, lambda: (messagebox.showerror("Errore FTP", error_msg), root.destroy()))
                return

            os.makedirs(LOCAL_IMPORT_DIR, exist_ok=True)
            os.makedirs(SAVE_DIR, exist_ok=True)

            if os.path.exists(SESSIONE_PATH):
                os.remove(SESSIONE_PATH)
            
            safe_progress("Attendi lo scaricamento dei file...")

            root.after(0, lambda: file_listbox.delete(0, tk.END))
            ftp.cwd(FTP_BASE_DIR)

            for fname in FILE_LIST:
                if terminate_import:
                    return
                try:
                    local_name = "PROMOZIONI" if fname == "PROMO" else fname
                    local_path = os.path.join(LOCAL_IMPORT_DIR, local_name)
                    with open(local_path, "wb") as f:
                        ftp.retrbinary(f"RETR " + fname, f.write)
                    pulisci_file_finale(local_path)
                    safe_insert(f"Scaricato: {fname}")
                    salva_copia(local_name)
                except:
                    safe_insert(f"Non trovato: {fname}")

            ftp.cwd(FTP_FATTURE_DIR)
            fatture_files = ftp.nlst()
            with open(DOCFOR_PATH, "wb") as docfor:
                for file in fatture_files:
                    if terminate_import:
                        return
                    ftp.retrbinary(f"RETR {file}", docfor.write)
                    safe_insert(f"Fattura → DOCFOR: {file}")
            salva_copia("DOCFOR")
            pulisci_file_finale(DOCFOR_PATH)

            ftp.quit()
            safe_progress("Attendere l'importazione dei file su STORE'...")

            imported_files = ["PROMOZIONI" if f == "PROMO" else f for f in FILE_LIST]
            imported_files.append("DOCFOR")

            while True:
                if terminate_import:
                    return

                sessione_esiste = os.path.exists(SESSIONE_PATH)
                file_presenti = [f for f in imported_files if os.path.exists(os.path.join(LOCAL_IMPORT_DIR, f))]

                if sessione_esiste and not file_presenti:
                    break  # Tutto ok, possiamo completare
                elif sessione_esiste and file_presenti:
                    try:
                        os.remove(SESSIONE_PATH)
                        safe_progress("In attesa che i file vengano elaborati...")
                    except Exception as e:
                        print(f"Errore rimozione sessione.txt: {e}")
                time.sleep(1)

            spinner_running = False
            safe_progress("Importazione completata con successo!")
            root.after(0, lambda: (messagebox.showinfo("Completato", "Importazione completata con successo."), root.destroy()))

        except Exception as e:
            spinner_running = False
            error_msg = f"{str(e)}"
            safe_progress(f"Errore: {error_msg}")
            root.after(0, lambda: messagebox.showerror("Errore", error_msg))

    threading.Thread(target=task).start()


btn_download = tk.Button(root, text="Scarica", font=("Arial", 12), command=run_import,
                         bg=BTN_COLOR, fg=FG_COLOR, activebackground="#444", activeforeground=FG_COLOR)
btn_download.pack(pady=10)


def on_close():
    global terminate_import
    if messagebox.askyesno("Conferma", "Vuoi interrompere l'importazione dei file?"):
        terminate_import = True
        root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()
