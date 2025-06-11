
import sys
import os
import threading
import tkinter as tk
from tkinter import messagebox
from ftplib import FTP
import time
from datetime import datetime
import shutil
from PIL import Image, ImageTk
from tkinter import PhotoImage
import xml.etree.ElementTree as ET



def load_ftp_config(xml_file_path="ftp_itscommconfig.xml"):
    tree = ET.parse(xml_file_path)
    root = tree.getroot()

    ftp = root.find("ftp")
    local = root.find("local")

    config = {
        "FTP_HOST": ftp.find("host").text,
        "FTP_USER": ftp.find("user").text,
        "FTP_PASS": ftp.find("password").text,
        "FTP_BASE_DIR": ftp.find("base_dir").text,
        "LOCAL_IMPORT_DIR": local.find("import_dir").text
    }

    config["FTP_FATTURE_DIR"] = f"{config['FTP_BASE_DIR']}/fatture"
    return config


ftp_config = load_ftp_config()

# === CONFIG ===
FTP_HOST = ftp_config["FTP_HOST"]
FTP_USER = ftp_config["FTP_USER"]
FTP_PASS = ftp_config["FTP_PASS"]
FTP_BASE_DIR = ftp_config["FTP_BASE_DIR"]
FTP_FATTURE_DIR = ftp_config["FTP_FATTURE_DIR"]
LOCAL_IMPORT_DIR = ftp_config["LOCAL_IMPORT_DIR"]
TEMP_IMPORT_DIR = os.path.join(LOCAL_IMPORT_DIR, "temporane")

FILE_LIST = ["ANAINT", "BARCODE", "ARTBIL", "VPREZZI", "PROMO"]
SAVE_DIR = os.path.join(LOCAL_IMPORT_DIR, "SAVE")
SESSIONE_PATH = os.path.join(LOCAL_IMPORT_DIR, "sessione.txt")
DOCFOR_PATH = os.path.join(TEMP_IMPORT_DIR, "DOCFOR")

# === STATO ===
import_started = False 
terminate_import = False  # flag di terminazione
import_thread = None


# === GUI Setup (tema scuro) ===
BG_COLOR = "#1e1e1e"
FG_COLOR = "#ffffff"
BTN_COLOR = "#66CC66"
HIGHLIGHT = "#555555"

root = tk.Tk()
root.title("Importazione File su STORE")
icon = PhotoImage(file="logo.png")

# Imposta l'icona per la finestra e la taskbar
root.iconphoto(True, icon)
root.configure(bg=BG_COLOR)
root.resizable(False, False)
window_width = 480
window_height = 450  # aumentato per far spazio al logo

# === Centro schermo e in primo piano ===
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
position_top = int(screen_height / 2 - window_height / 2)
position_left = int(screen_width / 2 - window_width / 2)
root.geometry(f"{window_width}x{window_height}+{position_left}+{position_top}")
root.attributes('-topmost', True)


info_label = tk.Label(
    root,
    text="PDV: 00103  ROSITANO",
    font=("Arial", 11),
    bg="#3a3a3a",
    fg="#ffffff",
    anchor="center",
    padx=10,
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

# === Nuovi elementi per animazione e logo ===
dots_frame = tk.Frame(root, bg=BG_COLOR)
dots_frame.pack()
dots_frame.pack_forget()

dots_labels = [
    tk.Label(dots_frame, text="●", font=("Arial", 18), fg=FG_COLOR, bg=BG_COLOR, height=1),
    tk.Label(dots_frame, text="●", font=("Arial", 18), fg=FG_COLOR, bg=BG_COLOR, height=1),
    tk.Label(dots_frame, text="●", font=("Arial", 18), fg=FG_COLOR, bg=BG_COLOR, height=1),
]
for lbl in dots_labels:
    lbl.pack(pady=0)

logo_img = None
logo_label = tk.Label(root, bg=BG_COLOR)


def animate_dots(counter=0):
    if terminate_import:
        return
    active = counter % 3
    for i, lbl in enumerate(dots_labels):
        lbl.config(fg=FG_COLOR if i == active else "#555555")
    root.after(300, lambda: animate_dots(counter + 1))


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # quando è un .exe
    except AttributeError:
        base_path = os.path.abspath('.')  # quando è un .py

    return os.path.join(base_path, relative_path)

def mostra_logo():
    global logo_img
    try:
        logo_path = resource_path("logo.png")
        logo_img = tk.PhotoImage(file=logo_path)
        logo_img = logo_img.subsample(5)  # Riduci la dimensione dell'i
        logo_label.config(image=logo_img)
        logo_label.pack(pady=0)
    except Exception as e:
        print("Errore caricamento logo:", e)


def salva_copia(nome_file):
    if terminate_import:
        return
    os.makedirs(SAVE_DIR, exist_ok=True)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    src = os.path.join(TEMP_IMPORT_DIR, nome_file)
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


def remove_selected_characters_from_file(path_file):
    # Define the special characters to be removed.
    # These are 0x1A (SUBSTITUTE) and 0x1C (FILE SEPARATOR).
    chars_to_remove = (0x1A, 0x1C)

    if not os.path.exists(path_file):
        print(f"[DEBUG] File {path_file} not found in remove_selected_characters_from_file.")
        return

    try:
        with open(path_file, "rb") as f:
            content = f.read()
    except Exception as e:
        print(f"Errore lettura file {path_file} in remove_selected_characters_from_file: {e}")
        return

    if not content:
        # Empty file, nothing to do or already processed to empty.
        return

    # Create new content by filtering out the unwanted characters.
    # This approach builds a new list of bytes.
    new_content_bytes = bytearray()
    modified = False
    for byte in content:
        if byte in chars_to_remove:
            modified = True
        else:
            new_content_bytes.append(byte)

    if modified:
        try:
            with open(path_file, "wb") as f:
                f.write(new_content_bytes)
            print(f"[DEBUG] Rimossi caratteri speciali ({', '.join(hex(c) for c in chars_to_remove)}) da {os.path.basename(path_file)}")
        except Exception as e:
            print(f"Errore scrittura file {path_file} in remove_selected_characters_from_file: {e}")
    # else: No special characters found, no need to rewrite the file.


def run_import():
    global import_started
    import_started = True
    def task():
        
        root.after(0, lambda: (
            btn_download.pack_forget(),
            dots_frame.pack(),
            animate_dots(),
            mostra_logo()
        ))

        try:
            safe_progress("Connessione all'FTP...")
            try:
                ftp = FTP(FTP_HOST)
                ftp.login(FTP_USER, FTP_PASS)
            except Exception as e:
                safe_progress("Errore di connessione FTP")
                error_msg = f"Impossibile connettersi all'FTP:\n{e}"
                root.after(0, lambda: (messagebox.showerror("Errore FTP", error_msg), root.destroy()))
                return

            os.makedirs(LOCAL_IMPORT_DIR, exist_ok=True)
            os.makedirs(TEMP_IMPORT_DIR, exist_ok=True)
            os.makedirs(SAVE_DIR, exist_ok=True)

            if os.path.exists(SESSIONE_PATH):
                os.remove(SESSIONE_PATH)

            safe_progress("Attendi lo scaricamento dei file...")

            root.after(0, lambda: file_listbox.delete(0, tk.END))
            ftp.cwd(FTP_BASE_DIR)

            files_presenti_ftp = ftp.nlst()  # Lista file presenti nella cartella principale FTP_BASE_DIR

            files_trovati = 0

            for fname in FILE_LIST:
                if terminate_import:
                    return
                if fname not in files_presenti_ftp:
                    continue
                try:
                    local_name = "PROMOZIONI" if fname == "PROMO" else fname
                    local_path = os.path.join(TEMP_IMPORT_DIR, local_name)
                    with open(local_path, "wb") as f:
                        ftp.retrbinary(f"RETR " + fname, f.write)
                    remove_selected_characters_from_file(local_path)
                    safe_insert(f"Scaricato: {fname}")
                    salva_copia(local_name)
                    files_trovati += 1
                except Exception as e:
                    print(f"Errore download file {fname}: {e}")

            # Ora controllo la cartella fatture (FTP_FATTURE_DIR)
            ftp.cwd(FTP_FATTURE_DIR)
            fatture_files = ftp.nlst()

            if fatture_files:  # Se ci sono file nelle fatture, li scarico e conto come file trovati
                with open(DOCFOR_PATH, "wb") as docfor:
                    for file in fatture_files:
                        if terminate_import:
                            return
                        ftp.retrbinary(f"RETR {file}", docfor.write)
                        safe_insert(f"Fattura → DOCFOR: {file}")
                salva_copia("DOCFOR")
                remove_selected_characters_from_file(DOCFOR_PATH)
                files_trovati += 1  # Segnalo che almeno un file di fatture è stato scaricato

            # Se non ho scaricato nessun file, esco e mostro messaggio
            if files_trovati == 0:
                with open(os.path.join(LOCAL_IMPORT_DIR, "sessione.txt"), "w") as f:
                    f.write("Nessun file da importare.\n")
                root.after(0, lambda: (
                    file_listbox.insert(tk.END, "Nessun file da importare."),
                    safe_progress("Nessun file da importare."),
                    dots_frame.pack_forget(),
                    logo_label.pack_forget()
                ))
                return


            ftp.quit()

            # Spostamento dei file da TEMP_IMPORT_DIR a LOCAL_IMPORT_DIR
            if os.path.exists(TEMP_IMPORT_DIR):
                safe_insert(f"Spostamento files da {TEMP_IMPORT_DIR} a {LOCAL_IMPORT_DIR}...")
                for filename in os.listdir(TEMP_IMPORT_DIR):
                    if terminate_import:
                        return # Check di terminazione anche durante lo spostamento
                    source_path = os.path.join(TEMP_IMPORT_DIR, filename)
                    destination_path = os.path.join(LOCAL_IMPORT_DIR, filename)
                    try:
                        shutil.move(source_path, destination_path)
                        safe_insert(f"Spostato: {filename} in {LOCAL_IMPORT_DIR}")
                    except Exception as e:
                        safe_insert(f"Errore spostamento {filename}: {e}")
                        # Potresti voler gestire l'errore in modo più specifico qui

                # Eliminazione della cartella temporanea dopo lo spostamento
                try:
                    shutil.rmtree(TEMP_IMPORT_DIR)
                    safe_insert(f"Cartella temporanea {TEMP_IMPORT_DIR} eliminata.")
                except Exception as e:
                    safe_insert(f"Errore eliminazione {TEMP_IMPORT_DIR}: {e}")
            else:
                safe_insert(f"Cartella temporanea {TEMP_IMPORT_DIR} non trovata per lo spostamento.")

            safe_progress("Attendere l'importazione dei file su STORE...")

            imported_files = [f.replace("PROMO", "PROMOZIONI") for f in FILE_LIST]
            imported_files.append("DOCFOR")

            while True:
                if terminate_import:
                    return
                sessione_esiste = os.path.exists(SESSIONE_PATH)
                file_presenti = [f for f in imported_files if os.path.exists(os.path.join(LOCAL_IMPORT_DIR, f))]
                if sessione_esiste and not file_presenti:
                    break
                elif sessione_esiste and file_presenti:
                    try:
                        os.remove(SESSIONE_PATH)
                        safe_progress("In attesa che i file vengano elaborati...")
                    except Exception as e:
                        print(f"Errore rimozione sessione.txt: {e}")
                time.sleep(1)

            safe_progress("L'importazione è quasi giunta al termine...")
            dots_frame.pack_forget(),
            logo_label.pack_forget()
            try:
                ftp = FTP(FTP_HOST)
                ftp.login(FTP_USER, FTP_PASS)
                ftp.cwd(FTP_BASE_DIR)
                for fname in FILE_LIST:
                    try:
                        ftp.delete(fname)
                    except:
                        pass
                ftp.cwd(FTP_FATTURE_DIR)
                for file in fatture_files:
                    try:
                        ftp.delete(file)
                    except:
                        pass
                ftp.quit()
            except Exception as e:
                print(f"Errore durante l'eliminazione dei file dall'FTP: {e}")

            safe_progress("Importazione completata con successo!")
            root.after(0, lambda: (
                dots_frame.pack_forget(),
                logo_label.pack_forget(),
                messagebox.showinfo("Completato", "Importazione completata con successo."),
                root.destroy()
            ))

        except Exception as e:
            error_msg = f"{str(e)}"
            safe_progress(f"Errore: {error_msg}")
            root.after(0, lambda: messagebox.showerror("Errore", error_msg))
            pass

    global import_thread
    import_thread = threading.Thread(target=task)
    import_thread.start()


def scarica_click_handler():
    # Non fare nulla se è già stato rilevato che non ci sono file
    if file_listbox.get(0) == "Nessun file da importare.":
        btn_download.config(state="disabled", bg="#555555")
        return
    run_import()

btn_download = tk.Button(root, text="Scarica File", font=("Arial", 12), command=scarica_click_handler,
                         bg=BTN_COLOR, fg=FG_COLOR, activebackground="#444", activeforeground=FG_COLOR)
btn_download.pack(pady=10)
        
def on_close():
    global terminate_import, import_started

    if import_thread and import_thread.is_alive():
        if not import_started:
            # Se il thread è attivo ma l'importazione non è partita, consenti chiusura
            root.destroy()
        else:
            # Importazione in corso e già partita: blocca la chiusura
            messagebox.showwarning("Attendere", "Operazione non valida. Attendi la fine dell'importazione!")
            return
    else:
        root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()
