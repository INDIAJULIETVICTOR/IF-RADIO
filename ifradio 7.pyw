# *
# * Project Name: Radio User Interface
# * File: ifradio.py
# *
# * Copyright (C) 2024 Fabrizio Palumbo (IU0IJV)
# * 
# * This program is distributed under the terms of the MIT license.
# * You can obtain a copy of the license at:
# * https://opensource.org/licenses/MIT
# *
# * DESCRIPTION:
# * Library implementation for interfacing with the Beken BK4819 radio module.
# *
# * AUTHOR: Fabrizio Palumbo
# * CREATION DATE: November, 4, 2024
# *
# * CONTACT: t.me/IU0IJV
# *
# * NOTES:
# * - This implementation includes functions for initializing and controlling the BK4819 module by PC
# * - Verify correct COM Port configuration before use.

import sys
import tkinter.ttk as ttk
from tkinter.constants import *
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import threading
import serial
import serial.tools.list_ports
import time
import queue
import math


COLOR_BACKGROUND = "#959595"
COLOR_FRAME_BACKGROUND = "cornsilk4"
COLOR_LABEL_FOREGROUND = "#efefef"
COLOR_LABEL_BACKGROUND = "#959595"
COLOR_BUTTON_ACTIVE_BG = "#696969"
COLOR_BUTTON_ACTIVE_FG = "black"
COLOR_BUTTON_BG = "#898989"
COLOR_BUTTON_FG = "#efefef"
COLOR_SCALE_TROUGH = "#898989"
COLOR_SCALE_BG = "#959595"
COLOR_SCALE_FG = "#efefef"
COLOR_ENTRY_BG = "#404040"
COLOR_ENTRY_FG = "#efefef"
COLOR_ENTRY_DISABLED_FG = "#68665a"
COLOR_DISPLAY_FG = "#efefef"
COLOR_DISPLAY_BG = "#404040"
COLOR_SLIDE_BG = "#898989"
COLOR_LED_GREEN = "#00FF00"


# Definizione degli indirizzi del protocollo CI-V
CIV_START_BYTE = 0xFE
CIV_END_BYTE = 0xFD
CIV_ADDRESS_RADIO = 0xE0        # Indirizzo radio di destinazione
CIV_ADDRESS_COMPUTER = 0x00     # Indirizzo del computer

COMMAND_SET_FREQUENCY = 0x05    # Comando per impostare la frequenza
COMMAND_GET_FREQUENCY = 0x03    # Comando per leggere la frequenza
COMMAND_SET_MODE = 0x06         # Comando per impostare la modalità operativa
COMMAND_SET_SQUELCH = 0x14      # Comando per impostare lo squelch
COMMAND_GET_SQUELCH = 0x15      # Comando per leggere il livello dello squelch
COMMAND_SET_AGC = 0x16          # Comando per impostare il tipo di AGC
COMMAND_GET_RSSI = 0x19         # Comando per ottenere il valore dello S-meter
COMMAND_SET_MONITOR = 0x1A      # comando per attivare o disattivare la funzioen monitor
COMMAND_SET_RFGAIN = 0x1C       # comando per settare il valore di RFGain
COMMAND_GET_RFGAIN = 0x1D       # comando per settare il valore di RFGain
COMMAND_SET_BANDWIDTH = 0x1E
COMMAND_GET_BANDWIDTH = 0x1F
COMMAND_SET_TX_POWER  = 0x20
COMMAND_GET_TX_POWER  = 0x21

COMMAND_SET_STEP = 0
COMMAND_SET_SCAN = 0

AGC_AUTO = 0
AGC_MAN = 1
AGC_SLOW = 2
AGC_NOR = 3
AGC_FAST = 4

MODE_AM = 0x00                  # Codice per AM
MODE_FM = 0x01                  # Codice per FM
MODE_SSB = 0x02                 # Codice per SSB
MODE_CW = 0x03                  # Codice per CW

modulazione=["AM","FM","SSB","CW"]
monitor =["   ","MON"]

_bgcolor = 'cornsilk4'
_fgcolor = 'black'
_tabfg1 = 'black' 
_tabfg2 = 'white' 
_bgmode = 'light' 
_tabbg1 = '#d9d9d9' 
_tabbg2 = 'gray40' 

_style_code_ran = 0

altezzavfo = 46
fontVFO = 25
fontLBL = 14
fontSTS = 10

monstat = 0

Led_activity_timeout = 0        # Timeout di 5 secondi di inattività della seriale


# Configurazione della porta seriale
try:
    ser = serial.Serial(
        port=None,            # Modifica con la porta corretta
        baudrate=115200,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.1
    )
except serial.SerialException as e:
    root = tk.Tk()
    root.withdraw()             # Nasconde la finestra principale
    messagebox.showerror("Errore Porta Seriale", f"Impossibile aprire la porta seriale: {e}")
    sys.exit(1)                 # Esci con errore

#-------------------------------------------------------------------------------------------------------------------------
# Funzioni Threading
#-------------------------------------------------------------------------------------------------------------------------
data_queue = queue.Queue()

# -----------------------------------------------------------------------------
# Thread per la gestione dei timeout

def led_timeout_manager():
    global Led_activity_timeout
    while True:
        if Led_activity_timeout > 0:
            Led_activity_timeout -= 1
            root.after(0, lambda: radio_panel.update_led(COLOR_LED_GREEN))
        else:
            # Spegni il LED se il timeout è scaduto
            root.after(0, lambda: radio_panel.update_led(COLOR_ENTRY_BG))

        time.sleep(1)  # Attendi 1 secondo

# -----------------------------------------------------------------------------
# Thread per la lettura dalla porta seriale

def read_from_port():
    
    buffer = bytearray()
    global ser
    global Led_activity_timeout
    
    while True:
        if ser and ser.is_open:
            try:
                if ser.in_waiting > 0:
                    # Leggi quanti più byte possibile per aumentare la velocità di lettura
                    data = ser.read(ser.in_waiting)
                    buffer.extend(data)
                    
                    # Aggiorna il LED a verde ogni volta che arrivano dati
                    Led_activity_timeout = 5

                    # Continua a elaborare tutti i messaggi completi nel buffer
                    while 0xFD in buffer:  # 0xFD rappresenta il byte di fine messaggio CI-V
                        end_index = buffer.index(0xFD)

                        # Estrai il messaggio completo
                        message = buffer[:end_index + 1]

                        # Verifica che il messaggio sia valido
                        if len(message) >= 6 and message[0] == 0xFE and message[1] == 0xFE:  # 0xFE rappresenta il byte di inizio messaggio CI-V
                            data_queue.put(message)

                        # Rimuovi il messaggio elaborato dal buffer
                        buffer = buffer[end_index + 1:]

            except serial.SerialException as e:
                print(f"Errore lettura seriale: {e}")
                break
            
        # Riduci al minimo il ritardo per massimizzare la frequenza di lettura
        time.sleep(0.1)
            

        
# -----------------------------------------------------------------------------
# Thread per elaborare i dati dalla coda

def process_data():
    while True:
        if not data_queue.empty():
            try:
                # Ottieni il messaggio dalla coda senza bloccare
                message = data_queue.get_nowait()
                # Elabora il messaggio CI-V
                process_civ_message(message)
            except queue.Empty:
                # In questo caso, l'eccezione non dovrebbe mai verificarsi, ma è bene gestirla
                pass
        else:
            # Se la coda è vuota, riduci il carico sulla CPU con una piccola pausa
            time.sleep(0.1)


# -----------------------------------------------------------------------------
transmission_enabled = True   # Flag globale per abilitare/disabilitare la trasmissione          

# -----------------------------------------------------------------------------
# Funzione per elaborare i messaggi CI-V ricevuti
def process_civ_message(message):

    global transmission_enabled

    try:
        # Decodifica il comando CI-V
        address_to = message[2]
        address_from = message[3]
        command = message[4]
        data = message[5:-1]  # Escludi l'ultimo byte (terminatore)

        # Aggiorna il display della frequenza quando si riceve il comando GET_FREQUENCY
        # -----------------------------------------------------------------------------
        if command == COMMAND_GET_FREQUENCY and len(data) > 0:
            
            # Decodifica la frequenza dai dati BCD ricevuti (da LSB a MSB)
            frequency = 0
            for i in range(len(data)):
                high_nibble = (data[i] >> 4) & 0x0F
                low_nibble = data[i] & 0x0F
                frequency = (frequency * 100) + (high_nibble * 10) + low_nibble
            
            # Chiamata al metodo di aggiornamento usando l'istanza singleton
            root.after(50, Toplevel1.instance.update_frequency_display, frequency)

        # Aggiorna il livello dello squelch quando si riceve il comando GET_SQUELCH
        # -----------------------------------------------------------------------------
        elif command == COMMAND_GET_SQUELCH and len(data) > 0:
            squelch_level = data[0]
            # Chiamata al metodo di aggiornamento dello squelch usando l'istanza singleton
            transmission_enabled = False
            root.after(0, Toplevel1.instance.update_squelch_display, squelch_level)
            root.after(0, lambda: SMeter.instance.update_squelch_threshold(squelch_level))


        # Aggiorna lo smeter con il segnale ricevuto
        # -----------------------------------------------------------------------------
        elif command == COMMAND_GET_RSSI and len(data) > 0:
            smeter_level = data[0] + data[1]*256
            # print(smeter_level);
            # Chiamata al metodo di aggiornamento dello squelch usando l'istanza singleton
            # root.after(0, Toplevel1.instance.update_smeter, smeter_level)
            root.after(0, SMeter.instance.update_smeter, smeter_level)

        # Aggiorna controllo rfgain
        # -----------------------------------------------------------------------------
        elif command == COMMAND_GET_RFGAIN and len(data) > 0:
            gain_level = data[0]
            # print(gain_level);
            # Chiamata al metodo di aggiornamento dello squelch usando l'istanza singleton
            transmission_enabled = False
            root.after(0, Toplevel1.instance.update_rfgain, gain_level)


    except Exception as e:
        print(f"Errore durante l'elaborazione del messaggio CI-V: {e}")

    # Riabilita la trasmissione dopo l'aggiornamento
    root.after(50, enable_transmission)
    

# Funzione per riabilitare la trasmissione
def enable_transmission():
    global transmission_enabled
    transmission_enabled = True

#-------------------------------------------------------------------------------------------------------------------------
# Funzioni per l'invio dei comandi alla radio
#-------------------------------------------------------------------------------------------------------------------------
# 
def send_command(command, data=[]):
    global ser

    if ser and ser.is_open:
        if transmission_enabled:
            message = [CIV_START_BYTE, CIV_START_BYTE, CIV_ADDRESS_RADIO, CIV_ADDRESS_COMPUTER, command] + data + [CIV_END_BYTE]
            ser.write(bytearray(message))
            ser.flushOutput()
    else:
        print("Porta seriale non aperta. Impossibile inviare il comando.")


def set_frequency(frequency):
    """
    Funzione per impostare la frequenza sulla radio secondo il protocollo CI-V.
    La frequenza deve essere passata in Hz.
    """
    # Convertire la frequenza in una stringa di 10 cifre per garantire il formato BCD
    frequency_str = f"{frequency:010d}"  # Assicura 10 cifre (es. 7410000 diventa 0007410000)
    data = [0x00] * 6  # Inizializza i 6 byte per i dati

    # Riempire i byte BCD secondo l'ordine specifico
    data[0] = (int(frequency_str[9]) << 4) | int(frequency_str[8])  # Byte 1: 10 Hz e 1 Hz
    data[1] = (int(frequency_str[7]) << 4) | int(frequency_str[6])  # Byte 2: 100 Hz e 1 kHz
    data[2] = (int(frequency_str[5]) << 4) | int(frequency_str[4])  # Byte 3: 10 kHz e 100 kHz
    data[3] = (int(frequency_str[3]) << 4) | int(frequency_str[2])  # Byte 4: 1 MHz e 10 MHz
    data[4] = (int(frequency_str[1]) << 4) | int(frequency_str[0])  # Byte 5: 100 MHz e 1 GHz
    data[5] = 0x00                                                  # Byte 6: opzionale, può essere utilizzato per altri scopi se necessario


    # Invia il comando alla radio
    send_command(COMMAND_SET_FREQUENCY, data)
    root.after(0, Toplevel1.instance.update_frequency_display, frequency)

    # Debug per verificare il valore inviato
    # print(f"Frequenza impostata (Hz): {frequency}")
    # print(f"Dati inviati (BCD): {[hex(b) for b in data]}")
    

def set_mode(mode):
    send_command(COMMAND_SET_MODE, [mode])
    root.after(0, lambda: radio_panel.update_vfo_status(0, mode=modulazione[mode]))

def set_rfgain(val):
    send_command(COMMAND_SET_RFGAIN, [val])

def set_monitor():
    data = [0x00, 0x01]
    send_command(COMMAND_SET_MONITOR, data)
    
    global monstat
    if monstat==0:
        monstat=1
    else:
        monstat=0
    root.after(0, lambda: radio_panel.update_vfo_status(0, mon=monitor[monstat]))
 
def set_squelch(squelch_level):
    send_command(COMMAND_SET_SQUELCH, [squelch_level])
    root.after(0, lambda: SMeter.instance.update_squelch_threshold(squelch_level))
    #time.sleep(0.05)

def set_agc():
    send_command(COMMAND_SET_AGC, 1)
    
def set_scan():
    send_command(COMMAND_SET_SCAN, 1)
    
def set_step():    
    send_command(COMMAND_SET_STEP, 1)    

def get_frequency():
    send_command(COMMAND_GET_FREQUENCY)

def get_squelch():
    send_command(COMMAND_GET_SQUELCH)

def get_rfgain():
    send_command(COMMAND_GET_RFGAIN)

def set_bw(val):
    send_command(COMMAND_SET_BANDWIDTH, [val])

def set_txpower(val):
    send_command(COMMAND_SET_TX_POWER, [val])

def periodic_update():
    if ser and ser.is_open:
        get_frequency()
        get_squelch()
        get_rfgain()
        # root.after(500, periodic_update)
    else:
        print("Porta seriale non aperta. Saltando aggiornamento periodico.")



def _style_code():
    global _style_code_ran
    if _style_code_ran: return        
    #try: ifradio_support.root.tk.call('source',os.path.join(_location, 'themes', 'clam.tcl'))
    #except: pass
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('.', font = "TkDefaultFont")
    _style_code_ran = 1


#-------------------------------------------------------------------------------------------------------------------------
# Definizione classe dei controlli grafici
#-------------------------------------------------------------------------------------------------------------------------
# 
class Toplevel1:

    instance = None  # Variabile di classe per mantenere l'unica istanza

    def __init__(self, top=None):
        
        self.ser = None         # Attributo per mantenere la connessione seriale

        if Toplevel1.instance is None:
            Toplevel1.instance = self  # Imposta l'istanza di classe solo se non è già stata creata

        top.geometry("900x310")
        top.title("IJV Radio Panel")
        top.configure(background=COLOR_BACKGROUND)
        top.configure(highlightbackground="cornsilk4")
        top.configure(highlightcolor="black")
        top.resizable(False, False)  # Impedisce il ridimensionamento sia in larghezza che in altezza

        self.top = top
        
        # Chiudi la connessione seriale all'uscita dell'app
        self.top.protocol("WM_DELETE_WINDOW", self.on_close)
        

        # Matrice per memorizzare i dati dei VFO (parametrico, ad esempio per VFO A e VFO B)
        self.vfo_status = [
            { "mode": "FM", "agc": "MAN", "bw": "U 6K", "step": "12.5K", "mon": "" },
            { "mode": "FM", "agc": "MAN", "bw": "U 6K", "step": "12.5K", "mon": "" }]

        # ---------------------------------------------------------------------------------------------Frame per lo S-meter
        # self.Frame_smeter = tk.Frame(self.top, background=COLOR_BACKGROUND, relief="flat", borderwidth=2, highlightbackground="cornsilk4", highlightcolor="black")
        # self.Frame_smeter.place(x=11, y=5, width=90, height=297) 

        # ----------------------------------------------------------- Label per indicare la funzione SIGNAL
        # self.Signal_label = tk.Label(
            # self.Frame_smeter,
            # text="SIGNAL",
            # font=("Segoe UI", 7, "bold"),
            # background=COLOR_BACKGROUND,
            # foreground=COLOR_LABEL_FOREGROUND,
            # anchor='w'
        # )
        # self.Signal_label.place(x=2, y=2, width=70, height=20)

        # ----------------------------------------------------------- Progressbar per S-meter
        # _style_code()  
        # self.smeter = ttk.Progressbar(
            # self.Frame_smeter,
            # orient="vertical",
            # length=19,
            # maximum=255,
            # value=10
        # )
        # self.smeter.place(x=11, y=22, width=18, height=259)

        #self.menubar = tk.Menu(top, font="TkMenuFont", bg='cornsilk4',fg=_fgcolor)
        #top.configure(menu = self.menubar)
        
        #--------------------------------------------------------------------------------------------- Frame Smeter
        
        # Definizione del frame principale per lo S-meter
        self.Frame_smeter = tk.Frame(self.top, background=COLOR_BACKGROUND, relief="flat", borderwidth=2, highlightbackground="cornsilk4", highlightcolor="black")
        self.Frame_smeter.place(x=20, y=26, width=220, height=120)  # Modifica le coordinate per assicurarti che sia visibile

        # Creazione di un'istanza di SMeter all'interno di Toplevel1
        self.smeter = SMeter(parent=self.Frame_smeter, scale_factor=0.5)
        self.smeter.pack(fill='both', expand=True)  # Riempie tutto lo spazio disponibile all'interno di Frame_smeter
        
        # Forza un aggiornamento dell'interfaccia
        #self.top.update()

        #--------------------------------------------------------------------------------------------- Frame Display
        # Creazione del frame per il display
        self.Frame_display = tk.Frame(self.top, background=COLOR_BACKGROUND, relief="flat", borderwidth=2)
        self.Frame_display.place(x=240, y=10, width=365, height=altezzavfo*4+40)
        #----------------------------------------------------------- Creazione del LabelFrame all'interno del frame di visualizzazione
        self.Labelframe1 = tk.LabelFrame(
            self.Frame_display,
            relief='flat',
            font=("Segoe UI", 9),
            foreground="black",
            background=COLOR_BACKGROUND,
            highlightbackground="cornsilk4",
            highlightcolor="black"
        )
        self.Labelframe1.place(x=10, y=10, width=360, height=175)

        #--------------------------------------------------------------------------------------------- Frame VFO e stato
        #----------------------------------------------------------- VFO A riga superiore
        # VFO A riga superiore
        self.VfoA = tk.Label(
            self.Labelframe1,
            text='0',
            font=("Consolas", fontVFO, "bold"),
            background=COLOR_DISPLAY_BG,
            foreground=COLOR_DISPLAY_FG,
            anchor='e',
            activebackground="#d9d9d9",
            activeforeground="black",
            compound='left',
            disabledforeground="#68665a",
            highlightbackground="cornsilk4",
            highlightcolor="black",
            padx="5"
        )
        self.VfoA.bind("<Button-1>", self.show_frequency_entry)
        self.VfoA.place(x=10, y=5, height=altezzavfo, width=296)

        self.VfoA_1 = tk.Label(
            self.Labelframe1,
            text='Hz',
            font=("Consolas", fontLBL, "bold"),
            background=COLOR_DISPLAY_BG,
            foreground=COLOR_DISPLAY_FG,
            anchor='e',
            activebackground="#d9d9d9",
            activeforeground="black",
            compound='left',
            disabledforeground="#68665a",
            highlightbackground="cornsilk4",
            highlightcolor="black",
            padx="15"
        )
        self.VfoA_1.place(x=300, y=5, height=altezzavfo, width=52)

        #----------------------------------------------------------- Riga di stato del VFO A
        self.StatusA = tk.Label(
            self.Labelframe1,
            text="",                      # Può essere aggiornato dinamicamente per mostrare lo stato
            font=("Consolas", fontSTS),          # Font più piccolo per i flag e le funzioni attive
            background=COLOR_DISPLAY_BG,
            foreground=COLOR_DISPLAY_FG,
            anchor='sw',
            activebackground="#d9d9d9",
            activeforeground="black",
            compound='left',
            disabledforeground="#68665a",
            highlightbackground="cornsilk4",
            highlightcolor="black",
            padx="10"
        )
        self.StatusA.place(x=10, y=altezzavfo + 5, height=int(altezzavfo / 2), width=362)

        #----------------------------------------------------------- Riga centrale per separare i VFO
        self.Separator = tk.Label(
            self.Labelframe1,
            text="",  # Può essere anche un testo più descrittivo se necessario
            font=("Consolas", fontSTS),
            background=COLOR_DISPLAY_BG,
            foreground=COLOR_DISPLAY_FG,
            anchor='center',
            activebackground="#d9d9d9",
            activeforeground="black",
            compound='left',
            disabledforeground="#68665a",
            highlightbackground="cornsilk4",
            highlightcolor="black"
        )
        self.Separator.place(x=10, y=altezzavfo + int(altezzavfo / 2) + 5 , height=int(altezzavfo / 2)+2, width=362)

        #----------------------------------------------------------- VFO B riga inferiore
        self.VfoB = tk.Label(
            self.Labelframe1,
            text='0',
            font=("Consolas", fontVFO, "bold"),
            background=COLOR_DISPLAY_BG,
            foreground=COLOR_DISPLAY_FG,
            anchor='e',
            activebackground="#d9d9d9",
            activeforeground="black",
            compound='left',
            disabledforeground="#68665a",
            highlightbackground="cornsilk4",
            highlightcolor="black",
            padx="5"
        )
        self.VfoB.place(x=10, y=altezzavfo*2 + 5, height=altezzavfo, width=296)

        self.VfoB_1 = tk.Label(
            self.Labelframe1,
            text='Hz',
            font=("Consolas", fontLBL, "bold"),
            background=COLOR_DISPLAY_BG,
            foreground=COLOR_DISPLAY_FG,
            anchor='e',
            activebackground="#d9d9d9",
            activeforeground="black",
            compound='left',
            disabledforeground="#68665a",
            highlightbackground="cornsilk4",
            highlightcolor="black",
            padx="15"
        )
        self.VfoB_1.place(x=300, y=altezzavfo*2 + 5,  height=altezzavfo, width=52)

        #----------------------------------------------------------- Riga di stato del VFO B
        self.StatusB = tk.Label(
            self.Labelframe1,
            text="",                                    # Può essere aggiornato dinamicamente per mostrare lo stato
            font=("Consolas", fontSTS),                 # Font più piccolo per i flag e le funzioni attive
            background=COLOR_DISPLAY_BG,
            foreground=COLOR_DISPLAY_FG,
            anchor='sw',
            activebackground="#d9d9d9",
            activeforeground="black",
            compound='left',
            disabledforeground="#68665a",
            highlightbackground="cornsilk4",
            highlightcolor="black",
            padx="10"
        )
        self.StatusB.place(x=10, y=altezzavfo*3 + 5, height=int(altezzavfo / 2), width=362)


        #--------------------------------------------------------------------------------------------- Frame Pulsanti
        # Creazione del frame per i pulsanti
        # Definizione del frame principale per i pulsanti
        self.Frame_pulsanti = tk.Frame(self.top, background=COLOR_BACKGROUND, relief="flat", borderwidth=2)
        self.Frame_pulsanti.place(x=10, y=190, width=600, height=130)

        # Definizione dei parametri comuni per i pulsanti
        button_params = {
            "background": COLOR_BUTTON_BG,
            "foreground": COLOR_BUTTON_FG,
            "activebackground": "#696969",
            "activeforeground": "black",
            "disabledforeground": "#68665a",
            "font": ("Consolas", 13, "bold"),
            "highlightbackground": "cornsilk4",
            "highlightcolor": "black",
            "padx": "6",
            "height": 26,
            "width": 62
        }

        # Definizione dei pulsanti con coordinate assolute
        buttons = [
            {"text": "AM", "command": lambda: set_mode(MODE_AM), "x": 10, "y": 25},
            {"text": "FM", "command": lambda: set_mode(MODE_FM), "x": 85, "y": 25},
            {"text": "SSB", "command": lambda: set_mode(MODE_SSB), "x": 160, "y": 25},
            {"text": "CW", "command": lambda: set_mode(MODE_CW), "x": 235, "y": 25},
            {"text": "SCAN", "command": lambda: set_scan(), "x": 310, "y": 25},
            {"text": "AGC", "command": lambda: set_agc(), "x": 385, "y": 25},
            {"text": "STEP", "command": lambda: set_step(), "x": 460, "y": 25},
            {"text": "MON", "command": lambda: set_monitor(), "x": 535, "y": 25},

            {"text": "NB", "command": lambda: set_nb(), "x": 10, "y": 70},
            {"text": "NOTCH", "command": lambda: set_notch(), "x": 85, "y": 70},
            {"text": "PRE", "command": lambda: set_pre(), "x": 160, "y": 70},
            {"text": "ATT", "command": lambda: set_att(), "x": 235, "y": 70},
            {"text": "RIT", "command": lambda: set_rit(), "x": 310, "y": 70},
            {"text": "XIT", "command": lambda: set_xit(), "x": 385, "y": 70},
            {"text": "ANT", "command": lambda: set_ant(), "x": 460, "y": 70},
            {"text": "TUNE", "command": lambda: set_tune(), "x": 535, "y": 70},
        ]

        # Creazione dei pulsanti all'interno del frame
        for btn in buttons:
            button = tk.Button(self.Frame_pulsanti, text=btn["text"], command=btn["command"])
            button.place(x=btn["x"], y=btn["y"], width=button_params["width"], height=button_params["height"])
            button.configure(**button_params)


        #----------------------------------------------------------- Creazione dei pulsanti utilizzando un ciclo

        #--------------------------------------------------------------------------------------------- Frame Cursori
        self.Frame_cursori = tk.Frame(self.top, background=COLOR_BACKGROUND, relief="flat", borderwidth=2)
        self.Frame_cursori.place(x=610, y=10, width=300, height=282)

        #------------------------------------------------------------------ RFGAIN
        # Label per indicare la funzione RF GAIN
        self.RfGain_label = tk.Label(
            self.Frame_cursori,
            text="RF GAIN",
            font=("Segoe UI", 7, "bold"),
            background=COLOR_BACKGROUND,
            foreground=COLOR_LABEL_FOREGROUND
        )
        self.RfGain_label.place(x=7, y=0, width=64, height=11)

        #----------------------------------------------------------- Scale per RF GAIN
        self.RfGain = tk.Scale(
            self.Frame_cursori,
            from_=31.0,
            to=0.0,
            resolution=1.0,
            command=lambda val: set_rfgain(int(val)),
            activebackground="#d9d9d9",
            background=COLOR_BACKGROUND,
            font=("Segoe UI", 8, "bold"),
            foreground=COLOR_LABEL_FOREGROUND,
            highlightbackground=COLOR_BACKGROUND,
            highlightcolor="black",
            length=266,
            troughcolor=COLOR_SLIDE_BG
        )
        self.RfGain.place(x=11, y=13, width=64, height=259)


        #------------------------------------------------------------------ SQUELCH
        # Label per indicare la funzione SQUELCH
        self.Squelch_label = tk.Label(
            self.Frame_cursori,
            text="SQUELCH",
            font=("Segoe UI", 7, "bold"),
            background=COLOR_BACKGROUND,
            foreground=COLOR_LABEL_FOREGROUND
        )
        self.Squelch_label.place(x=71, y=0, width=67, height=11)

        #----------------------------------------------------------- Scale per SQUELCH
        self.Squelch = tk.Scale(
            self.Frame_cursori,
            from_=255.0,
            to=0.0,
            resolution=1.0,
            command=lambda val: set_squelch(int(val)),
            activebackground="#d9d9d9",
            background=COLOR_BACKGROUND,
            font=("Segoe UI", 8, "bold"),
            foreground=COLOR_LABEL_FOREGROUND,
            highlightbackground=COLOR_BACKGROUND,
            highlightcolor="black",
            length=246,
            troughcolor=COLOR_SLIDE_BG
        )
        self.Squelch.place(x=71, y=13, width=67, height=259)

        # Timer per debouncing
        self.squelch_timer = None
        self.Squelch.bind("<ButtonRelease-1>", self.schedule_squelch_update)
        self.Squelch.bind("<Motion>", self.schedule_squelch_update)


        #------------------------------------------------------------------ BANDWITH
        # Label per indicare la funzione SET BW
        self.bw_label = tk.Label(
            self.Frame_cursori,
            text="SET BW",
            font=("Segoe UI", 7, "bold"),
            background=COLOR_BACKGROUND,
            foreground=COLOR_LABEL_FOREGROUND
        )
        self.bw_label.place(x=146, y=0, width=64, height=11)

        #----------------------------------------------------------- Label per mostrare il valore selezionato accanto al cursore
        self.bandwidth_value_label = tk.Label(
            self.Frame_cursori,
            text="U06K",
            font=("Segoe UI", 8, "bold"),
            background=COLOR_BACKGROUND,
            foreground=COLOR_LABEL_FOREGROUND
        )
        self.bandwidth_value_label.place(x=132, y=252, anchor='w')

        #----------------------------------------------------------- Scale per SET BW
        self.bw = tk.Scale(
            self.Frame_cursori,
            from_=9.0,
            to=0.0,
            resolution=1.0,
            command=self.update_bandwidth_label,
            showvalue=False,
            activebackground="#d9d9d9",
            background=COLOR_BACKGROUND,
            font=("Segoe UI", 8, "bold"),
            foreground=COLOR_LABEL_FOREGROUND,
            highlightbackground=COLOR_BACKGROUND,
            highlightcolor="black",
            length=266,
            troughcolor=COLOR_SLIDE_BG
        )
        self.bw.place(x=166, y=13, width=64, height=259)

        #------------------------------------------------------------------ TX POWER Control
        self.txp_label = tk.Label(
            self.Frame_cursori, 
            text="TX POWER", 
            font=("Segoe UI", 7, "bold"),
            background=COLOR_BACKGROUND,
            foreground=COLOR_LABEL_FOREGROUND
        )
        self.txp_label.place(x=213, y=0, width=64, height=11)
        
        #-----------------------------------------------------------
        self.txp = tk.Scale(
            self.Frame_cursori, 
            from_=15.0, 
            to=0.0, 
            resolution=1.0, 
            command=lambda val: set_txpower(int(val)),
            activebackground="#d9d9d9",
            background=COLOR_BACKGROUND,
            font=("Segoe UI", 8, "bold"),
            foreground=COLOR_LABEL_FOREGROUND,
            highlightbackground=COLOR_BACKGROUND,
            highlightcolor="black",
            length=266,
            troughcolor=COLOR_SLIDE_BG
        )
        self.txp.place(x=213, y=13, width=64, height=259)
        self.update_vfo_status(0, bw="U06K")
        self.update_vfo_status(1, bw="U06K")
        root.after(500, periodic_update)
        
        #-----------------------------------------------------------
        
        #----------------------------------------------------------- Frame per la selezione della porta seriale
        serial_frame = tk.Frame(root, bg=COLOR_BACKGROUND, width=200, height=25)
        serial_frame.place(x=25, y=165)  # Posiziona il frame con coordinate assolute

        # Label per la selezione della porta seriale
        port_label = tk.Label(serial_frame, text="COM PORT :", bg=COLOR_BACKGROUND, fg=COLOR_LABEL_FOREGROUND, font=("Segoe UI", 8, "bold"))
        port_label.place(x=0, y=2)

        #----------------------------------------------------------- Combobox per la selezione della porta
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("CustomCombobox.TCombobox", fieldbackground=COLOR_BACKGROUND, background=COLOR_BACKGROUND, foreground=COLOR_LABEL_FOREGROUND)

        self.port_combobox = ttk.Combobox(serial_frame, state="readonly", width=10, style="CustomCombobox.TCombobox")
        self.port_combobox.place(x=75, y=2)

        # Carica le porte disponibili all'avvio
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combobox['values'] = ports  # Aggiorna la lista di opzioni della Combobox

        #----------------------------------------------------------- LED indicatore di connessione
        self.connection_led = tk.Label(serial_frame, bg=COLOR_ENTRY_BG, width=5, height=1, relief="solid", bd=1)
        self.connection_led.place(x=170, y=2)  # Posiziona il LED accanto alla Combobox

        # Associa la selezione della porta alla funzione on_port_selected
        self.port_combobox.bind("<<ComboboxSelected>>", self.on_port_selected)

    #-------------------------------------------------------------------------------------------------------------------------
    # Definizione funzioni della classe
    #-------------------------------------------------------------------------------------------------------------------------
    # 
    # Funzione per aprire la connessione alla porta selezionata
    def on_port_selected(self, event=None):
        selected_port = self.port_combobox.get()
        self.open_serial_connection(selected_port)

    def update_led(self, color):
        # Cambia il colore del LED in base al parametro `color`
        self.connection_led.config(bg=color)

    # Funzione per aprire la connessione seriale in modo sicuro
    def open_serial_connection(self, selected_port='COM11'):
        global ser  # Usa `ser` come variabile globale
        try:
            # Chiude la connessione seriale se già aperta
            if self.ser and self.ser.is_open:
                self.ser.close()
                #print("Connessione seriale precedente chiusa.")
                time.sleep(0.5)  # Pausa per assicurare che la porta sia rilasciata

            # Apre la nuova connessione seriale
            self.ser = serial.Serial(
                port=selected_port,
                baudrate=115200,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            ser = self.ser
            #print(f"Connessione aperta su {selected_port}, ser globale è {ser}")

            # Avvia periodic_update dopo aver aperto la connessione
            self.top.after(500, periodic_update)

        except serial.SerialException as e:
            print(f"Errore nella connessione: {e}")
      
    # Funzione per chiudere la connessione seriale all'uscita dell'app
    def on_close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            #print("Connessione seriale chiusa all'uscita.")
        self.top.destroy()  # Chiudi la finestra principale

    def show_frequency_entry(self, event):
        """Sostituisce l'etichetta della frequenza con un widget Entry per l'inserimento della frequenza."""
        # Rimuovi la label corrente
        self.VfoA.place_forget()

        # Crea un Entry per inserire la nuova frequenza con lo stesso stile del Label
        
        # Usare una f-string per formattare la stringa del font
        self.frequency_entry = tk.Entry(
            self.Labelframe1,
            font=("Consolas", fontVFO, "bold"),  # Usa la notazione a tupla per specificare il font
            justify='right',
            relief='flat',
            borderwidth=0
        )
        self.frequency_entry.place(x=10, y=5, height=altezzavfo, width=291)
        self.frequency_entry.insert(0, self.VfoA.cget("text"))  # Inserisci il valore attuale nel campo di input

        # Configura il colore di sfondo e il colore del testo per il Entry in modo che corrispondano alla Label
        self.frequency_entry.configure(
            bg=self.VfoA.cget("background"),
            fg=self.VfoA.cget("foreground"),
            disabledforeground=self.VfoA.cget("disabledforeground"),
            insertbackground=self.VfoA.cget("foreground")  # Colore del cursore (di inserimento)
        )
        self.frequency_entry.focus()  # Metti il focus sull'Entry per facilitare l'inserimento

        # Aggiungi binding per cancellare il valore corrente al primo tasto premuto
        self.frequency_entry.bind("<Key>", self.clear_entry)

        # Aggiungi binding per confermare l'inserimento con Enter
        self.frequency_entry.bind("<Return>", self.set_frequency_from_entry)

        # Aggiungi binding per perdere il focus
        self.frequency_entry.bind("<FocusOut>", self.restore_frequency_label)

    def clear_entry(self, event):
        """Cancella il valore dell'Entry al primo tasto premuto."""
        self.frequency_entry.delete(0, tk.END)
        # Dopo la prima cancellazione, rimuovi il binding per evitare ulteriori cancellazioni
        self.frequency_entry.unbind("<Key>")

    def set_frequency_from_entry(self, event):
        """Aggiorna la frequenza in base al valore inserito e ripristina la label."""
        try:
            frequency_str = self.frequency_entry.get()
            frequency = int(frequency_str)              # Converti il valore in un intero
            set_frequency(frequency)                    # Funzione per inviare il comando alla radio
            self.update_frequency_display(frequency)    # Aggiorna il display della frequenza
        except ValueError:
            print("Inserire un valore numerico valido per la frequenza")
            # Potresti anche aggiungere un messaggio di errore nella GUI

        # Ripristina la label della frequenza immediatamente dopo aver premuto Enter
        self.restore_frequency_label()

    def restore_frequency_label(self, event=None):
        """Ripristina l'etichetta della frequenza e rimuove il widget Entry."""
        if hasattr(self, 'frequency_entry'):
            # Rimuovi l'Entry
            self.frequency_entry.destroy()  # Usa destroy per eliminare l'Entry completamente

        # Ripristina la label per visualizzare la frequenza
        self.VfoA.place(x=12, y=7, height=altezzavfo, width=296, bordermode='ignore')

        # Riapplica il binding per il click sul label
        self.VfoA.bind("<Button-1>", self.show_frequency_entry)

    def update_frequency_display(self, frequency):
        """Aggiorna il valore mostrato nel Label della frequenza."""
        frequency_str = f"{frequency:08d}"
        formatted_frequency = f"{int(frequency_str):,}".replace(",", ".")
        self.VfoA.config(text=formatted_frequency)

    def schedule_squelch_update(self, event):
        if self.squelch_timer:
            self.top.after_cancel(self.squelch_timer)  # Annulla il timer precedente
        self.squelch_timer = self.top.after(200, lambda: set_squelch(self.Squelch.get()))

    def update_frequency_display(self, frequency):
        # Aggiorna la visualizzazione della frequenza
        frequency_str = f"{frequency:08d}"
        formatted_frequency = f"{int(frequency_str):,}".replace(",", ".")
        self.VfoA.config(text=formatted_frequency)

    def update_rfgain(self, gain_level):
        # Aggiorna la visualizzazione dell'RF Gain
        self.RfGain.set(gain_level)

    def update_squelch_display(self, squelch_level):
        # Aggiorna la visualizzazione dello squelch
        self.Squelch.set(squelch_level)

    def update_smeter(self, smeter_level):
        # Aggiorna la visualizzazione dello S-meter
        self.smeter["value"] = smeter_level

    def update_bandwidth_label(self, value):
        # Lista di opzioni discrete per la larghezza di banda
        bandwidth_options = ["U06K","U07K","N09K","N10K","W12K","W14K","W17K","W20K","W23K","W26K" ]

        # Converti il valore dello slide in un indice nella lista delle opzioni
        selected_bandwidth = bandwidth_options[int(value)]

        # Aggiorna la label per mostrare il valore selezionato
        self.bandwidth_value_label.config(text=f"{selected_bandwidth}")

        # Calcola la posizione verticale in base al valore del cursore
        max_slider_value = self.bw.cget("from")  # Valore massimo dello slider
        slider_length = self.bw.cget("length")-45 # Lunghezza totale dello slider

        # Calcola la posizione della label in base al valore corrente
        step_size = slider_length / max_slider_value
        slider_pos = (int(float(value)) * step_size)
        
        # Posiziona la label in coordinate assolute accanto allo slider
        self.bandwidth_value_label.place(x=132, y=252-slider_pos, anchor='w')  # y è basato sul valore dello slider
        
        set_bw(int(value))
        self.update_vfo_status(0, bw=selected_bandwidth)
 
    # Funzione per aggiornare la visualizzazione della riga di stato di un VFO specifico
    def update_status(self, vfo_index):
        status_text = (
            f"{self.vfo_status[vfo_index]['mode']:<3} "
            f"{self.vfo_status[vfo_index]['agc']:<4} "
            f"{self.vfo_status[vfo_index]['bw']:<4} "
            f"{self.vfo_status[vfo_index]['step']:<5} "
            f"{self.vfo_status[vfo_index]['mon']:<3} "
        )

        # Aggiorna la visualizzazione di stato per il VFO A o B
        if vfo_index == 0:
            self.StatusA.config(text=status_text)
        elif vfo_index == 1:
            self.StatusB.config(text=status_text)

    # Funzione per aggiornare uno o più parametri del dizionario di un VFO specifico
    def update_vfo_status(self, vfo_index, **kwargs):
        # Controllo per assicurarsi che l'indice del VFO sia valido
        if 0 <= vfo_index < len(self.vfo_status):
            # Aggiorna i valori nel dizionario del VFO specificato
            for key, value in kwargs.items():
                if key in self.vfo_status[vfo_index]:
                    self.vfo_status[vfo_index][key] = value
            # Aggiorna la visualizzazione per il VFO specifico
            self.update_status(vfo_index)
        else:
            print(f"Indice VFO non valido: {vfo_index}")

#-------------------------------------------------------------------------------------------------------------------------
# 
#-------------------------------------------------------------------------------------------------------------------------
#   
class SMeter(tk.Frame):
    instance = None  # Definizione di una variabile di classe per tenere traccia dell'istanza

    def __init__(self, parent, scale_factor=1.0, x=0, y=0):
        super().__init__(parent, bd=5, relief="sunken", bg="#a0a0a0")
        self.parent = parent
        self.scale_factor = scale_factor    # Usa il valore passato come argomento
        self.squelch_threshold = 0          # Valore iniziale della soglia dello squelch
        self.current_value = 0              # Valore iniziale della lancetta
        self.needle = None                  # Inizializza la lancetta come None
        self.rssi_value = 0                 # Valore iniziale RSSI
        self.s_meter_value = "S0"           # Valore iniziale scala S

        # Assegna l'istanza corrente alla variabile di classe
        SMeter.instance = self

        # Creazione del Frame principale per il misuratore
        self.configure(bg="#959595")
        self.place(x=x, y=y)                # Posiziona il frame alle coordinate x, y

        # Applica il ridimensionamento e la costruzione del layout
        self.apply_scaling()

        # Inizializza la lancetta
        self.update_needle(self.current_value)

    def create_meter_canvas(self):
        # Rimuove il canvas precedente se esistente
        if hasattr(self, 'canvas'):
            self.canvas.destroy()

        # Dimensioni del canvas per disegnare l'S-meter
        canvas_width = int(404 * self.scale_factor)
        canvas_height = int(204 * self.scale_factor)  # Altezza ridotta del canvas per diminuire lo spazio in alto
        self.canvas = tk.Canvas(self, width=canvas_width, height=canvas_height, bg="#e0e0e0", highlightthickness=0, bd=2, relief="ridge")
        self.canvas.place(x=0, y=0)                   # Riduce lo spazio sopra (padding superiore più piccolo)

        # Centro del misuratore
        self.center_x = canvas_width // 2
        self.center_y = canvas_height                 # Coordinate Y ridotte per alzare il contenuto
        self.radius = int(150 * self.scale_factor)

        # Disegno del quadrante
        self.draw_meter_scale()
        
        # Aggiungi il valore RSSI in basso a sinistra
        self.rssi_label = self.canvas.create_text(
            20,                                       # Coordinata X (vicino alla parte sinistra del canvas)
            canvas_height - 10,                       # Coordinata Y (vicino alla parte inferiore del canvas)
            text=f"RSSI: {self.rssi_value} dBm",
            anchor='w',
            font=("Segoe UI", max(8, int(12 * self.scale_factor)), "bold"),
            fill="black"
        )

        # Aggiungi il valore in scala S in basso a destra
        self.s_meter_label = self.canvas.create_text(
            canvas_width - 20,                        # Coordinata X (vicino alla parte destra del canvas)
            canvas_height - 10,                       # Coordinata Y (vicino alla parte inferiore del canvas)
            text=f"S: {self.s_meter_value}",
            anchor='e',
            font=("Segoe UI", max(8, int(12 * self.scale_factor)), "bold"),
            fill="black"
        )
 
    def draw_meter_scale(self):
        # Disegna una scala semicircolare con segni principali per S3-S9, +10, +30, +60
        label_positions = {
            0: "S", 10: "3", 25: "5", 40: "7", 50: "9", 60: "+10", 80: "+30", 100: "+60"
        }

        # Disegna i segni e le etichette
        for value in range(0, 101, 5):  # Segni ogni 5 unità
            angle = math.radians(150 - (value / 100) * 120)  # Scala invertita
            x_start = self.center_x + self.radius * math.cos(angle)
            y_start = self.center_y - self.radius * math.sin(angle)

            if value % 20 == 0:
                x_end = self.center_x + (self.radius - int(20 * self.scale_factor)) * math.cos(angle)
                y_end = self.center_y - (self.radius - int(20 * self.scale_factor)) * math.sin(angle)
                width = max(2, int(3 * self.scale_factor))  # Larghezza minima aumentata per tacche principali
                color = "black" if value < 60 else "red"
            else:
                x_end = self.center_x + (self.radius - int(10 * self.scale_factor)) * math.cos(angle)
                y_end = self.center_y - (self.radius - int(10 * self.scale_factor)) * math.sin(angle)
                width = max(1, int(1.5 * self.scale_factor))  # Larghezza minima aumentata per tacche secondarie
                color = "black"
            self.canvas.create_line(x_start, y_start, x_end, y_end, width=width, fill=color)

        # Aggiungi le etichette sopra la scala
        for value, label in label_positions.items():
            angle = math.radians(150 - (value / 100) * 120)  # Scala invertita
            x_text = self.center_x + (self.radius + int(25 * self.scale_factor)) * math.cos(angle)  # Posiziona sopra i segni della scala
            y_text = self.center_y - (self.radius + int(25 * self.scale_factor)) * math.sin(angle)
            self.canvas.create_text(x_text, y_text, text=label, font=("Segoe UI", max(8, int(14 * self.scale_factor)), "bold"))

        #----------------------------------------------------------- Disegna l'arco rosso sottile per i valori tra +10 e +60
        self.canvas.create_arc(
            self.center_x - (self.radius - int(12 * self.scale_factor)),  # Riduci il raggio
            self.center_y - (self.radius - int(12 * self.scale_factor)),  # Riduci il raggio
            self.center_x + (self.radius - int(12 * self.scale_factor)),  # Riduci il raggio
            self.center_y + (self.radius - int(12 * self.scale_factor)),  # Riduci il raggio
            start=30, extent=60, outline="red", width=max(2, int(6 * self.scale_factor)), style="arc"
        )

        #----------------------------------------------------------- Disegna l'arco nero sottile per i valori tra S e +60
        self.canvas.create_arc(
            self.center_x - (self.radius - int(20 * self.scale_factor)),  # Riduci il raggio di 20 pixel
            self.center_y - (self.radius - int(20 * self.scale_factor)),  # Riduci il raggio di 20 pixel
            self.center_x + (self.radius - int(20 * self.scale_factor)),  # Riduci il raggio di 20 pixel
            self.center_y + (self.radius - int(20 * self.scale_factor)),  # Riduci il raggio di 20 pixel
            start=150, extent=-120, outline="#404040", width=max(2, int(2 * self.scale_factor)), style="arc"
        )
        
        #----------------------------------------------------------- Disegna l'arco verde per la soglia dello squelch
        squelch_angle = 150 - ((self.squelch_threshold) / 255) * 120  # Calcola l'angolo per la soglia dello squelch

        # Limita l'angolo minimo dell'arco per non superare +60 dB (30 gradi)
        squelch_angle = max(min(round(squelch_angle), 150), 30)
        
        self.canvas.create_arc(
            self.center_x - (self.radius - int(30 * self.scale_factor)),
            self.center_y - (self.radius - int(30 * self.scale_factor)),
            self.center_x + (self.radius - int(30 * self.scale_factor)),
            self.center_y + (self.radius - int(30 * self.scale_factor)),
            start=150, extent=-(150 - squelch_angle), outline="green", width=max(2, int(6 * self.scale_factor)), style="arc"
        )

        # Aggiungi la scritta "SIGNAL" al centro
        self.canvas.create_text(self.center_x, self.center_y - int(80 * self.scale_factor), text="SIGNAL", font=("Segoe UI", max(10, int(21 * self.scale_factor)), "bold"))

    def update_needle(self, value):
        # Converte il valore in un intero
        target_value = int(value)

        # Anima la lancetta fino al valore target
        step = 1 if target_value > self.current_value else -1

        for val in range(self.current_value, target_value + step, step):
            self.draw_needle(val)
            self.current_value = val
            self.update()
            time.sleep(0.005)  # Ritardo per l'animazione

    def draw_needle(self, value):
        # Calcola l'angolo della lancetta in base al valore (da 150° a 30°)
        angle = math.radians(150 - (value / 100) * 120)

        # Coordinate della punta della lancetta
        needle_x = self.center_x + self.radius * 0.85 * math.cos(angle)
        needle_y = self.center_y - self.radius * 0.85 * math.sin(angle)

        # Rimuovi la lancetta precedente (se esiste)
        if self.needle:
            self.canvas.delete(self.needle)

        # Disegna la nuova lancetta
        width = max(2, int(2 * self.scale_factor))  # Larghezza della lancetta con valore minimo
        self.needle = self.canvas.create_line(self.center_x, self.center_y, needle_x, needle_y, width=width, fill="red")

    def apply_scaling(self):
        # Applica il ridimensionamento iniziale
        self.create_meter_canvas()

        # Reimposta la lancetta per garantire che venga disegnata correttamente dopo il ridimensionamento
        self.draw_needle(self.current_value)
        
    def update_smeter(self, valore):
        # Conversione del valore della radio (da 0 a 255) in dB
        livello_dB = (valore / 2) - 160
        self.rssi_value = round(livello_dB, 1)  # Aggiorna il valore RSSI

        # Definizione della tabella di conversione dBm a livelli S
        livelli_s = [
            (-147, 0), (-141, 1), (-135, 2), (-129, 3), (-123, 4),
            (-117, 5), (-111, 6), (-105, 7), (-99, 8), (-93, 9),  # S0 - S9
            (-83, 10), (-73, 11), (-63, 12), (-53, 13)  # S9+10, S9+20, S9+30
        ]

        # Trova l'intervallo corrispondente per livello_dB
        smeter_value = 0  # Valore di default, nel caso non rientri negli intervalli
        for i in range(len(livelli_s) - 1):
            (dBm_min, s_min) = livelli_s[i]
            (dBm_max, s_max) = livelli_s[i + 1]

            if dBm_min <= livello_dB <= dBm_max:
                # Interpolazione lineare per ottenere un valore continuo tra s_min e s_max
                frazione = (livello_dB - dBm_min) / (dBm_max - dBm_min)
                smeter_value = s_min + frazione * (s_max - s_min)
                break

        # Assegna direttamente i valori estremi se il livello è fuori intervallo
        if livello_dB < livelli_s[0][0]:
            smeter_value = 0
        elif livello_dB > livelli_s[-1][0]:
            smeter_value = 13

        # Normalizza il valore S su una scala da 0 a 100 per la visualizzazione della lancetta
        if smeter_value <= 9:
            smeter_target_value = (smeter_value / 9) * 52  # Scala compresa tra 0 e 75 per i valori da S0 a S9
        else:
            # Comprimere l'incremento dopo S9 per evitare che vada troppo velocemente oltre S9+10
            smeter_target_value = 58 + ((smeter_value - 9) / 4) * 20  # Da 75 a 100 per valori da S9+ in poi

        # Aggiorna il valore in scala S per la visualizzazione
        if smeter_value < 9:
            # Mostra il valore arrotondato per S0-S9
            self.s_meter_value = f"{int(round(smeter_value))}"
        else:
            # Dopo S9, utilizza il formato S9+XX per rappresentare +10, +20, ecc.
            increment = int((smeter_value - 9) * 10)
            self.s_meter_value = f"9+{increment}"

        # Richiama la funzione di smussamento per aggiornare la lancetta in modo graduale
        self.smooth_update_needle(smeter_target_value)

        # Aggiorna le etichette RSSI e S-meter
        self.canvas.itemconfig(self.rssi_label, text=f"RSSI: {self.rssi_value} dBm")
        self.canvas.itemconfig(self.s_meter_label, text=f"S: {self.s_meter_value}")

            
        # print(f"livello_dB: {livello_dB}, smeter_value: {smeter_value}, S-meter visualizzato: {self.s_meter_value}")


        
    def update_squelch_threshold(self, squelch_threshold):
        # Aggiorna il valore della soglia dello squelch
        self.squelch_threshold = squelch_threshold

        # Ridisegna il canvas per aggiornare la visualizzazione della soglia
        self.create_meter_canvas()
            
        # Dopo aver ridisegnato il canvas, riposiziona la lancetta
        self.draw_needle(self.current_value)
            
            
    def smooth_update_needle(self, target_value):
        # Definizione dei passi per il movimento in avanti e all'indietro
        step_forward = 10.0  # Passo maggiore per l'avanzamento rapido
        step_backward = 1  # Passo minore per il ritorno lento

        # Soglia minima per evitare oscillazioni
        dead_zone = 0.5  # Tolleranza per fermare l'aggiornamento

        # Determina se avanzare o retrocedere
        if abs(self.current_value - target_value) <= dead_zone:
            self.current_value = target_value
            self.draw_needle(self.current_value)
            return  # Ferma l'aggiornamento se è nella zona morta

        if target_value > self.current_value:
            # Movimento rapido in avanti
            self.current_value = min(self.current_value + step_forward, target_value)
        elif target_value < self.current_value:
            # Movimento lento indietro
            self.current_value = max(self.current_value - step_backward, target_value)

        # Disegna la lancetta con il nuovo valore corrente
        self.draw_needle(self.current_value)

        # Richiama se stesso finché il target non viene raggiunto
        self.after(10, self.smooth_update_needle, target_value)





        
#-------------------------------------------------------------------------------------------------------------------------
# 
#-------------------------------------------------------------------------------------------------------------------------
# 
       
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("800x600")  # Assicurati che ci sia abbastanza spazio nella finestra principale
    radio_panel = Toplevel1(root)

    # Avvio del thread di lettura seriale
    serial_thread = threading.Thread(target=read_from_port, daemon=True)
    serial_thread.start()

    # Esegui il thread per la gestione dei dati
    processing_thread = threading.Thread(target=process_data, daemon=True)
    processing_thread.start()
    
    # Esegui il thread per il timeout
    timeout_thread = threading.Thread(target=led_timeout_manager, daemon=True)
    timeout_thread.start()

    transmission_enabled = True
    root.after(1000, get_frequency)     # Ritardo più lungo per dare tempo alla seriale di stabilizzarsi
    root.after(600, get_squelch)
    root.after(700, get_rfgain)
  
    root.mainloop()
