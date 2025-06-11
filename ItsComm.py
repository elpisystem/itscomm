
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


def trim_trailing_special_chars(path_file):
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


def remove_lines_with_special_chars(path_file):
    if not os.path.exists(path_file):
        return

    line_delimiter = b'*'
    special_chars = (0x1A, 0x1C) # SUB and FS

    try:
        with open(path_file, "rb") as f:
            content = f.read()
    except Exception as e:
        print(f"Errore lettura file {path_file} in remove_lines_with_special_chars: {e}")
        return

    if not content:
        return # Empty file, nothing to do

    # Split content into lines. If content ends with delimiter, split will produce an empty string at the end.
    lines = content.split(line_delimiter)

    # Determine if original content ended with a delimiter.
    # This is important for reconstructing the trailing delimiter if all lines are kept or some lines are kept.
    original_ended_with_delimiter = content.endswith(line_delimiter)

    cleaned_lines = []
    modified = False
    for i, line_bytes in enumerate(lines):
        # If the original content ended with a delimiter, the last "line" from split() will be empty.
        # We should not check this empty part for special characters if it's just due to a trailing delimiter.
        if i == len(lines) - 1 and line_bytes == b'' and original_ended_with_delimiter:
            # This is the empty part after the last delimiter, keep it as is to preserve trailing delimiter later
            cleaned_lines.append(line_bytes)
            continue

        contains_special_char = False
        for byte_val in line_bytes:
            if byte_val in special_chars:
                contains_special_char = True
                break

        if contains_special_char:
            modified = True
        else:
            cleaned_lines.append(line_bytes)

    if modified:
        # Reconstruct the content.
        # If cleaned_lines is empty (all lines removed), new_content will be empty.
        # If cleaned_lines has one item (which was empty itself, from a file like "*"),
        # joining it results in empty, then add delimiter.
        # If cleaned_lines has ["line1",""], joining gives "line1*", if it was ["line1"], gives "line1"

        new_content = line_delimiter.join(cleaned_lines)

        # Handle the case where all lines are removed. new_content would be b''
        # If original_ended_with_delimiter was true, and new_content is not empty,
        # or if new_content is empty but it was originally just "*", it should end with a delimiter.
        # A simpler rule: if the cleaned list is not identical to just a single empty string (which means all actual lines were removed from a file that was not just "*"),
        # and the original ended with a delimiter, ensure the new one also does.
        # Or, more simply: if there's any content left, or if the original file was just "*" or "content*", ensure the trailing delimiter.

        # If all lines were removed, new_content is b''.
        # If some lines remain, or if the file was originally only `b"*"` (cleaned_lines = [b'', b''])
        # and the first part is kept, it should end with b'*'

        # Let's refine the trailing delimiter logic for reconstruction:
        # 1. If all lines were removed, new_content is empty. This is correct.
        # 2. If some lines remain:
        #    The `lines.split(delimiter)` behavior:
        #    - b"line1*line2*".split(b'*') -> [b'line1', b'line2', b'']
        #    - b"line1*line2".split(b'*')  -> [b'line1', b'line2'] (WRONG ASSUMPTION, split always makes last empty if ends with)
        #    Actually, `content.split(line_delimiter)` is fine. If content ends with `*`, last element of `lines` is `b''`.
        #    If this `b''` is preserved in `cleaned_lines` (because it's the last element and `original_ended_with_delimiter` is true),
        #    then `line_delimiter.join(cleaned_lines)` will correctly end with a delimiter.
        #    Example: lines = [b'good', b'bad', b''], special in 'bad'. cleaned_lines = [b'good', b'']. join -> b'good*'
        #    Example: lines = [b'good1', b'good2', b''], no special. cleaned_lines = [b'good1', b'good2', b''] -> join -> b'good1*good2*'
        #    Example: lines = [b'bad', b''], special in 'bad'. cleaned_lines = [b'']. join -> b'' (This needs care if original was just "*")

        # If cleaned_lines is [b''], it means either all actual lines were removed leaving only the trailing empty part,
        # or the original file was just b"*".
        if new_content == b'' and original_ended_with_delimiter and not (len(cleaned_lines) == 1 and cleaned_lines[0] == b''):
             # This case is tricky: if all actual content lines are removed, new_content is b''.
             # We probably don't want to add back a '*' if it's truly empty.
             # If original was `b"bad*"` -> lines `[b'bad', b'']`. cleaned_lines `[b'']`. new_content `b''`. Correct.
             # If original was `b"*"` -> lines `[b'', b'']`. cleaned_lines `[b'', b'']`. new_content `b'*'`. Correct.
             pass # Let join handle it.

        try:
            with open(path_file, "wb") as f:
                f.write(new_content)
            print(f"[DEBUG] Rimosse righe con caratteri speciali da {os.path.basename(path_file)} usando '*' come delimitatore.")
        except Exception as e:
            print(f"Errore scrittura file {path_file} in remove_lines_with_special_chars: {e}")
    # else: no modification needed, don't rewrite the file


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
                    remove_lines_with_special_chars(local_path)
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
                trim_trailing_special_chars(DOCFOR_PATH)
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
