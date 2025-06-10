import os
import time
from ftplib import FTP
from datetime import datetime
import shutil
import logging

# === CONFIG ===
FTP_HOST = "affiliati.diperspesa.it"
FTP_USER = "GCAFF103"
FTP_PASS = "$af103user"
FTP_BASE_DIR = "/Gescom/ftpaffiliati/00103"
FTP_FATTURE_DIR = f"{FTP_BASE_DIR}/fatture"
FILE_LIST = ["ANAINT", "BARCODE", "ARTBIL", "VPREZZI", "PROMO"]  

IMPORT_DIR = r"C:\ITSHOP\STORE\USER\IMPORT"
SAVE_DIR = os.path.join(IMPORT_DIR, "SAVE")
LOG_DIR = os.path.join(IMPORT_DIR, "LOG")
SESSIONE_PATH = os.path.join(IMPORT_DIR, "sessione.txt")
DOCFOR_PATH = os.path.join(IMPORT_DIR, "DOCFOR")

# === LOGGING ===
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
log_filename = f"LOGIMPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
log_path = os.path.join(LOG_DIR, log_filename)
logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s - %(message)s")

def salva_copia(nome_file):
    src = os.path.join(IMPORT_DIR, nome_file)
    if os.path.exists(src):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(SAVE_DIR, f"{timestamp}_{nome_file}")
        shutil.copy2(src, dst)
        logging.info(f"Copia salvata: {dst}")

def main():
    try:
        logging.info("== AVVIO IMPORTAZIONE ==")

        # Connessione FTP
        ftp = FTP(FTP_HOST)
        ftp.login(FTP_USER, FTP_PASS)
        logging.info("Connessione FTP riuscita")

        os.makedirs(IMPORT_DIR, exist_ok=True)

        if os.path.exists(SESSIONE_PATH):
            os.remove(SESSIONE_PATH)
            logging.info("File sessione.txt eliminato")

        ftp.cwd(FTP_BASE_DIR)

        # Scarica file principali
        for fname in FILE_LIST:
            try:
                local_name = "PROMOZIONI" if fname == "PROMO" else fname
                local_path = os.path.join(IMPORT_DIR, local_name)
                with open(local_path, "wb") as f:
                    ftp.retrbinary(f"RETR " + fname, f.write)
                logging.info(f"Scaricato: {fname}")
                salva_copia(local_name)
            except Exception as e:
                logging.warning(f"Non trovato o errore su {fname}: {e}")

        # Scarica tutte le fatture in DOCFOR
        ftp.cwd(FTP_FATTURE_DIR)
        fatture_files = ftp.nlst()
        with open(DOCFOR_PATH, "wb") as docfor:
            for file in fatture_files:
                ftp.retrbinary(f"RETR {file}", docfor.write)
                logging.info(f"Aggiunta a DOCFOR: {file}")
        salva_copia("DOCFOR")

        ftp.quit()
        logging.info("FTP disconnesso")

        # Attesa sessione.txt
        logging.info("Attesa creazione file sessione.txt...")
        while not os.path.exists(SESSIONE_PATH):
            time.sleep(1)

        logging.info("File sessione.txt trovato — importazione completata.")

    except Exception as e:
        logging.error(f"Errore durante l'importazione: {e}")

if __name__ == "__main__":
    main()
