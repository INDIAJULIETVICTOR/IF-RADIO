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
import time
import queue



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

_bgcolor = 'cornsilk4'
_fgcolor = 'black'
_tabfg1 = 'black' 
_tabfg2 = 'white' 
_bgmode = 'light' 
_tabbg1 = '#d9d9d9' 
_tabbg2 = 'gray40' 

_style_code_ran = 0

altezzavfo = 56

# Configurazione della porta seriale
try:
    ser = serial.Serial(
        port='COM11',               # Modifica con la porta corretta
        baudrate=115200,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.1
    )
except serial.SerialException as e:
    root = tk.Tk()
    root.withdraw()  # Nasconde la finestra principale
    messagebox.showerror("Errore Porta Seriale", f"Impossibile aprire la porta seriale: {e}")
    sys.exit(1)  # Esci con errore


#-------------------------------------------------------------------------------------------------------------------------
# Funzioni Threading
#-------------------------------------------------------------------------------------------------------------------------
data_queue = queue.Queue()

# -----------------------------------------------------------------------------
# funzione che legge dalla porta seriale

def read_from_port(ser):
    buffer = bytearray()
    while True:
        try:
            if ser.in_waiting > 0:
                # Leggi quanti più byte possibile per aumentare la velocità di lettura
                data = ser.read(ser.in_waiting)
                buffer.extend(data)

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

            # Riduci al minimo il ritardo per massimizzare la frequenza di lettura
            time.sleep(0.1)

        except serial.SerialException as e:
            print(f"Errore lettura seriale: {e}")
            break

        
# -----------------------------------------------------------------------------
# Definisci la funzione per elaborare i dati dalla coda

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
# Flag globale per abilitare/disabilitare la trasmissione
transmission_enabled = True                

# -----------------------------------------------------------------------------
# Funzione per elaborare i messaggi CI-V
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

        # Aggiorna lo smeter con il segnale ricevuto
        # -----------------------------------------------------------------------------
        elif command == COMMAND_GET_RSSI and len(data) > 0:
            smeter_level = data[0]
            # print(smeter_level);
            # Chiamata al metodo di aggiornamento dello squelch usando l'istanza singleton
            root.after(0, Toplevel1.instance.update_smeter, smeter_level)

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
    global transmission_enabled

    if transmission_enabled == True:
        message = [CIV_START_BYTE, CIV_START_BYTE, CIV_ADDRESS_RADIO, CIV_ADDRESS_COMPUTER, command] + data + [CIV_END_BYTE]
        ser.write(bytearray(message))
        ser.flushOutput()

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

def set_rfgain(val):
    send_command(COMMAND_SET_RFGAIN, [val])

def set_monitor():
    data = [0x00, 0x01]
    send_command(COMMAND_SET_MONITOR, data)

def set_squelch(squelch_level):
    send_command(COMMAND_SET_SQUELCH, [squelch_level])
    time.sleep(0.05)

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
    get_frequency()
    get_squelch()
    # root.after(500, periodic_update)






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
        if Toplevel1.instance is None:
            Toplevel1.instance = self  # Imposta l'istanza di classe solo se non è già stata creata

        top.geometry("700x290")
        top.title("IJV Radio Panel")
        top.configure(background="#959595")
        top.configure(highlightbackground="cornsilk4")
        top.configure(highlightcolor="black")
        top.resizable(False, False)  # Impedisce il ridimensionamento sia in larghezza che in altezza

        self.top = top

        #---------------------------------------------------------------------------------------------Frame per lo S-meter
        self.Frame_smeter = tk.Frame(self.top)
        self.Frame_smeter = tk.Frame(self.top, background="#959595", relief="flat", borderwidth=2, highlightbackground="cornsilk4", highlightcolor="black")
        self.Frame_smeter.place(x=13, y=9, width=47, height=297)

        # Label per indicare la funzione SIGNAL
        self.Signal_label = tk.Label(self.Frame_smeter)
        self.Signal_label.place(relx=0.1, rely=0.0, relwidth=0.8, relheight=0.05)
        self.Signal_label.configure(text="SIGNAL")
        self.Signal_label.configure(font="-family {Segoe UI} -size 7 -weight bold")
        self.Signal_label.configure(background="#959595")
        self.Signal_label.configure(foreground="#efefef")

        # Progressbar per S-meter
        _style_code()
        self.smeter = ttk.Progressbar(self.Frame_smeter)
        self.smeter.place(relx=0.25, rely=0.06, relwidth=0.5, relheight=0.85)  # Regolato rely per allineare meglio
        self.smeter.configure(orient="vertical")
        self.smeter.configure(length="19")
        self.smeter.configure(maximum="255")
        self.smeter.configure(value='10')



        self.menubar = tk.Menu(top, font="TkMenuFont", bg='cornsilk4',fg=_fgcolor)
        top.configure(menu = self.menubar)

        #--------------------------------------------------------------------------------------------- Frame Display
        self.Frame_display = tk.Frame(self.top)
        self.Frame_display = tk.Frame(self.top, background="#959595", relief="flat", borderwidth=2)
        self.Frame_display.place(x=50, y=10, width=365, height=193)


        self.Labelframe1 = tk.LabelFrame(self.Frame_display)
        self.Labelframe1.place(relx=0.027, rely=0.052, relheight=0.907, relwidth=0.986)
        self.Labelframe1.configure(relief='flat')
        self.Labelframe1.configure(font="-family {Segoe UI} -size 9")
        self.Labelframe1.configure(foreground="black")
        self.Labelframe1.configure(relief="flat")
        self.Labelframe1.configure(background="#959595")
        self.Labelframe1.configure(highlightbackground="cornsilk4")
        self.Labelframe1.configure(highlightcolor="black")

        #--------------------------------------------------------------------------------------------- VFO A riga superiore
        self.VfoA = tk.Label(self.Labelframe1)
        self.VfoA.bind("<Button-1>", self.show_frequency_entry)
        self.VfoA.place(relx=0.028, rely=0.057, height=altezzavfo, width=296, bordermode='ignore')
        self.VfoA.configure(activebackground="#d9d9d9")
        self.VfoA.configure(activeforeground="black")
        self.VfoA.configure(anchor='e')
        self.VfoA.configure(background="#404040")
        self.VfoA.configure(compound='left')
        self.VfoA.configure(disabledforeground="#68665a")
        self.VfoA.configure(font="-family {Consolas} -size 24 -weight bold")
        self.VfoA.configure(foreground="#efefef")
        self.VfoA.configure(highlightbackground="cornsilk4")
        self.VfoA.configure(highlightcolor="black")
        self.VfoA.configure(padx="5")
        self.VfoA.configure(text='''0''')

        self.VfoA_1 = tk.Label(self.Labelframe1)
        self.VfoA_1.place(relx=0.839, rely=0.057, height=altezzavfo, width=52, bordermode='ignore')
        self.VfoA_1.configure(activebackground="#d9d9d9")
        self.VfoA_1.configure(activeforeground="black")
        self.VfoA_1.configure(anchor='e')
        self.VfoA_1.configure(background="#404040")
        self.VfoA_1.configure(compound='left')
        self.VfoA_1.configure(disabledforeground="#68665a")
        self.VfoA_1.configure(font="-family {Consolas} -size 18 -weight bold")
        self.VfoA_1.configure(foreground="#efefef")
        self.VfoA_1.configure(highlightbackground="cornsilk4")
        self.VfoA_1.configure(highlightcolor="black")
        self.VfoA_1.configure(padx="15")
        self.VfoA_1.configure(text='''Hz''')

        #--------------------------------------------------------------------------------------------- Riga centrale
        self.Status = tk.Label(self.Labelframe1)
        self.Status.place(relx=0.028, rely=0.343, height=altezzavfo, width=341, bordermode='ignore')
        self.Status.configure(activebackground="#d9d9d9")
        self.Status.configure(activeforeground="black")
        self.Status.configure(anchor='e')
        self.Status.configure(background="#404040")
        self.Status.configure(compound='left')
        self.Status.configure(disabledforeground="#68665a")
        self.Status.configure(font="-family {Consolas} -size 19")
        self.Status.configure(foreground="#efefef")
        self.Status.configure(highlightbackground="cornsilk4")
        self.Status.configure(highlightcolor="black")
        self.Status.configure(padx="15")        

        #--------------------------------------------------------------------------------------------- VFO B riga inferiore
        self.VfoB = tk.Label(self.Labelframe1)
        self.VfoB.place(relx=0.028, rely=0.629, height=altezzavfo, width=296, bordermode='ignore')
        self.VfoB.configure(activebackground="#d9d9d9")
        self.VfoB.configure(activeforeground="black")
        self.VfoB.configure(anchor='e')
        self.VfoB.configure(background="#404040")
        self.VfoB.configure(compound='left')
        self.VfoB.configure(disabledforeground="#68665a")
        self.VfoB.configure(font="-family {Consolas} -size 24 -weight bold")
        self.VfoB.configure(foreground="#efefef")
        self.VfoB.configure(highlightbackground="cornsilk4")
        self.VfoB.configure(highlightcolor="black")
        self.VfoB.configure(padx="5")
        self.VfoB.configure(text='''0''')

        self.VfoB_1 = tk.Label(self.Labelframe1)
        self.VfoB_1.place(relx=0.839, rely=0.629, height=altezzavfo, width=52, bordermode='ignore')
        self.VfoB_1.configure(activebackground="#d9d9d9")
        self.VfoB_1.configure(activeforeground="black")
        self.VfoB_1.configure(anchor='e')
        self.VfoB_1.configure(background="#404040")
        self.VfoB_1.configure(compound='left')
        self.VfoB_1.configure(disabledforeground="#68665a")
        self.VfoB_1.configure(font="-family {Consolas} -size 18 -weight bold")
        self.VfoB_1.configure(foreground="#efefef")
        self.VfoB_1.configure(highlightbackground="cornsilk4")
        self.VfoB_1.configure(highlightcolor="black")
        self.VfoB_1.configure(padx="15")
        self.VfoB_1.configure(text='''Hz''')

        #--------------------------------------------------------------------------------------------- Frame Pulsanti
        self.Frame_pulsanti = tk.Frame(self.top)
        self.Frame_pulsanti = tk.Frame(self.top, background="#959595", relief="flat", borderwidth=2)
        self.Frame_pulsanti.place(x=70, y=190, width=365, height=130)


        self.PB_AM = tk.Button(self.Frame_pulsanti, text='AM', command=lambda: set_mode(MODE_AM))
        self.PB_AM.place(relx=0.029, rely=0.147, height=26, width=67)
        self.PB_AM.configure(activebackground="#696969")
        self.PB_AM.configure(activeforeground="black")
        self.PB_AM.configure(background="#898989")
        self.PB_AM.configure(disabledforeground="#68665a")
        self.PB_AM.configure(font="-family {Consolas} -size 14 -weight bold")
        self.PB_AM.configure(foreground="#efefef")
        self.PB_AM.configure(highlightbackground="#d4d4d4")
        self.PB_AM.configure(highlightcolor="black")
        self.PB_AM.configure(padx="6")
        self.PB_AM.configure(text='''AM''')

        self.PB_FM = tk.Button(self.Frame_pulsanti, text='FM', command=lambda: set_mode(MODE_FM))
        self.PB_FM.place(relx=0.262, rely=0.147, height=26, width=67)
        self.PB_FM.configure(activebackground="#696969")
        self.PB_FM.configure(activeforeground="black")
        self.PB_FM.configure(background="#898989")
        self.PB_FM.configure(disabledforeground="#68665a")
        self.PB_FM.configure(font="-family {Consolas} -size 14 -weight bold")
        self.PB_FM.configure(foreground="#efefef")
        self.PB_FM.configure(highlightbackground="cornsilk4")
        self.PB_FM.configure(highlightcolor="black")
        self.PB_FM.configure(padx="6")
        self.PB_FM.configure(text='''FM''')

        self.PB_SSB = tk.Button(self.Frame_pulsanti, text='SSB', command=lambda: set_mode(MODE_SSB))
        self.PB_SSB.place(relx=0.494, rely=0.147, height=26, width=67)
        self.PB_SSB.configure(activebackground="#696969")
        self.PB_SSB.configure(activeforeground="black")
        self.PB_SSB.configure(background="#898989")
        self.PB_SSB.configure(disabledforeground="#68665a")
        self.PB_SSB.configure(font="-family {Consolas} -size 14 -weight bold")
        self.PB_SSB.configure(foreground="#efefef")
        self.PB_SSB.configure(highlightbackground="cornsilk4")
        self.PB_SSB.configure(highlightcolor="black")
        self.PB_SSB.configure(padx="6")
        self.PB_SSB.configure(text='''SSB''')

        self.PB_CW = tk.Button(self.Frame_pulsanti)
        self.PB_CW.place(relx=0.727, rely=0.147, height=26, width=67)
        self.PB_CW.configure(activebackground="#696969")
        self.PB_CW.configure(activeforeground="black")
        self.PB_CW.configure(background="#898989")
        self.PB_CW.configure(disabledforeground="#68665a")
        self.PB_CW.configure(font="-family {Consolas} -size 14 -weight bold")
        self.PB_CW.configure(foreground="#efefef")
        self.PB_CW.configure(highlightbackground="cornsilk4")
        self.PB_CW.configure(highlightcolor="black")
        self.PB_CW.configure(padx="6")
        self.PB_CW.configure(text='''CW''')

        self.PB_SCAN = tk.Button(self.Frame_pulsanti, text='SCAN', command=lambda: set_scan())
        self.PB_SCAN.place(relx=0.029, rely=0.447, height=26, width=67)
        self.PB_SCAN.configure(activebackground="#696969")
        self.PB_SCAN.configure(activeforeground="black")
        self.PB_SCAN.configure(background="#898989")
        self.PB_SCAN.configure(disabledforeground="#68665a")
        self.PB_SCAN.configure(font="-family {Consolas} -size 14 -weight bold")
        self.PB_SCAN.configure(foreground="#efefef")
        self.PB_SCAN.configure(highlightbackground="#d4d4d4")
        self.PB_SCAN.configure(highlightcolor="black")
        self.PB_SCAN.configure(padx="6")
        self.PB_SCAN.configure(text='''SCAN''')

        self.PB_AGC = tk.Button(self.Frame_pulsanti, text='AGC', command=lambda: set_agc())
        self.PB_AGC.place(relx=0.262, rely=0.447, height=26, width=67)
        self.PB_AGC.configure(activebackground="#696969")
        self.PB_AGC.configure(activeforeground="black")
        self.PB_AGC.configure(background="#898989")
        self.PB_AGC.configure(disabledforeground="#68665a")
        self.PB_AGC.configure(font="-family {Consolas} -size 14 -weight bold")
        self.PB_AGC.configure(foreground="#efefef")
        self.PB_AGC.configure(highlightbackground="cornsilk4")
        self.PB_AGC.configure(highlightcolor="black")
        self.PB_AGC.configure(padx="6")
        self.PB_AGC.configure(text='''AGC''')

        self.PB_STEP = tk.Button(self.Frame_pulsanti, text='STEP', command=lambda: set_step())
        self.PB_STEP.place(relx=0.494, rely=0.447, height=26, width=67)
        self.PB_STEP.configure(activebackground="#696969")
        self.PB_STEP.configure(activeforeground="black")
        self.PB_STEP.configure(background="#898989")
        self.PB_STEP.configure(disabledforeground="#68665a")
        self.PB_STEP.configure(font="-family {Consolas} -size 14 -weight bold")
        self.PB_STEP.configure(foreground="#efefef")
        self.PB_STEP.configure(highlightbackground="cornsilk4")
        self.PB_STEP.configure(highlightcolor="black")
        self.PB_STEP.configure(padx="6")
        self.PB_STEP.configure(text='''STEP''')

        self.PB_MON = tk.Button(self.Frame_pulsanti, text='MON', command=lambda: set_monitor())
        self.PB_MON.place(relx=0.727, rely=0.447, height=26, width=67)
        self.PB_MON.configure(activebackground="#696969")
        self.PB_MON.configure(activeforeground="black")
        self.PB_MON.configure(background="#898989")
        self.PB_MON.configure(disabledforeground="#68665a")
        self.PB_MON.configure(font="-family {Consolas} -size 14 -weight bold")
        self.PB_MON.configure(foreground="#efefef")
        self.PB_MON.configure(highlightbackground="cornsilk4")
        self.PB_MON.configure(highlightcolor="black")
        self.PB_MON.configure(padx="6")
        self.PB_MON.configure(text='''MON''')

        #--------------------------------------------------------------------------------------------- Frame Cursori
        self.Frame_cursori = tk.Frame(self.top, background="#959595", relief="flat", borderwidth=2)
        self.Frame_cursori.place(x=415, y=10, width=300, height=282)

        #------------------------------------------------------------------ RFGAIN
        # Label per indicare la funzione RF Gain
        self.RfGain_label = tk.Label(self.Frame_cursori)
        self.RfGain_label.place(x=11, y=0, width=64, height=11)
        self.RfGain_label.configure(text="RF GAIN")
        self.RfGain_label.configure(font="-family {Segoe UI} -size 7 -weight bold")
        self.RfGain_label.configure(background="#959595")
        self.RfGain_label.configure(foreground="#efefef")

        # Scale per RF Gain
        self.RfGain = tk.Scale(self.Frame_cursori, from_=31.0, to=0.0, resolution=1.0, command=lambda val: set_rfgain(int(val)))
        self.RfGain.place(x=11, y=13, width=64, height=259)

        self.RfGain.configure(activebackground="#d9d9d9")
        self.RfGain.configure(background="#959595")
        self.RfGain.configure(font="-family {Segoe UI} -size 8 -weight bold")
        self.RfGain.configure(foreground="#efefef")
        self.RfGain.configure(highlightbackground="#959595")
        self.RfGain.configure(highlightcolor="black")
        self.RfGain.configure(length="266")
        self.RfGain.configure(troughcolor="#898989")

        #------------------------------------------------------------------ SQUELCH
        # Label per indicare la funzione Squelch
        self.Squelch_label = tk.Label(self.Frame_cursori)
        self.Squelch_label.place(x=71, y=0, width=67, height=11)

        self.Squelch_label.configure(text="SQUELCH")
        self.Squelch_label.configure(font="-family {Segoe UI} -size 7 -weight bold")
        self.Squelch_label.configure(background="#959595")
        self.Squelch_label.configure(foreground="#efefef")

        # Scale per Squelch
        self.Squelch = tk.Scale(self.Frame_cursori, from_=255.0, to=0.0, resolution=1.0, command=lambda val: set_squelch(int(val)))
        self.Squelch.place(x=71, y=13, width=67, height=259)

        self.Squelch.configure(activebackground="#d9d9d9")
        self.Squelch.configure(background="#959595")
        self.Squelch.configure(font="-family {Segoe UI} -size 8 -weight bold")
        self.Squelch.configure(foreground="#efefef")
        self.Squelch.configure(highlightbackground="#959595")
        self.Squelch.configure(highlightcolor="black")
        self.Squelch.configure(length="246")
        self.Squelch.configure(troughcolor="#898989")

        self.squelch_timer = None  # Per il debouncing
        self.Squelch.bind("<ButtonRelease-1>", self.schedule_squelch_update)
        self.Squelch.bind("<Motion>", self.schedule_squelch_update)


        #------------------------------------------------------------------ BANDWITH
        # Label per indicare la funzione RF Gain
        self.bw_label = tk.Label(self.Frame_cursori)
        self.bw_label.place(x=146, y=0, width=64, height=11)
        self.bw_label.configure(text="SET BW")
        self.bw_label.configure(font="-family {Segoe UI} -size 7 -weight bold")
        self.bw_label.configure(background="#959595")
        self.bw_label.configure(foreground="#efefef")

        # Label per mostrare il valore selezionato accanto al cursore 
        self.bandwidth_value_label = tk.Label(self.Frame_cursori, text="U06K", font=("Segoe UI", 8, "bold"), background="#959595", foreground="#efefef")
        self.bandwidth_value_label.place(x=132, y=252, anchor='w') 

        # Scale per RF Gain
        self.bw = tk.Scale(self.Frame_cursori, from_=9.0, to=0.0, resolution=1.0, command=self.update_bandwidth_label, showvalue=False)
        self.bw.place(x=166, y=13, width=64, height=259)

        self.bw.configure(activebackground="#d9d9d9")
        self.bw.configure(background="#959595")
        self.bw.configure(font="-family {Segoe UI} -size 8 -weight bold")
        self.bw.configure(foreground="#efefef")
        self.bw.configure(highlightbackground="#959595")
        self.bw.configure(highlightcolor="black")
        self.bw.configure(length="266")
        self.bw.configure(troughcolor="#898989")


        #------------------------------------------------------------------ TXPOWER
        # Label per indicare la funzione RF Gain
        self.txp_label = tk.Label(self.Frame_cursori)
        self.txp_label.place(x=213, y=0, width=64, height=11)
        self.txp_label.configure(text="TX POWER")
        self.txp_label.configure(font="-family {Segoe UI} -size 7 -weight bold")
        self.txp_label.configure(background="#959595")
        self.txp_label.configure(foreground="#efefef")

        # Scale per RF Gain
        self.txp = tk.Scale(self.Frame_cursori, from_=15.0, to=0.0, resolution=1.0, command=lambda val: set_txpower(int(val)))
        self.txp.place(x=213, y=13, width=64, height=259)

        self.txp.configure(activebackground="#d9d9d9")
        self.txp.configure(background="#959595")
        self.txp.configure(font="-family {Segoe UI} -size 8 -weight bold")
        self.txp.configure(foreground="#efefef")
        self.txp.configure(highlightbackground="#959595")
        self.txp.configure(highlightcolor="black")
        self.txp.configure(label="")
        self.txp.configure(length="266")
        self.txp.configure(troughcolor="#898989")


        root.after(500, periodic_update)


    def show_frequency_entry(self, event):
        """Sostituisce l'etichetta della frequenza con un widget Entry per l'inserimento della frequenza."""
        # Rimuovi la label corrente
        self.VfoA.place_forget()

        # Crea un Entry per inserire la nuova frequenza con lo stesso stile del Label
        self.frequency_entry = tk.Entry(self.Labelframe1, font="-family {Consolas} -size 24 -weight bold", justify='right', relief='flat', borderwidth=0)
        self.frequency_entry.place(relx=0.028, rely=0.057, height=altezzavfo, width=291, bordermode='ignore')  # Larghezza ridotta per compensare il padx
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
        self.VfoA.place(relx=0.028, rely=0.057, height=altezzavfo, width=296, bordermode='ignore')

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


#-------------------------------------------------------------------------------------------------------------------------
# 
#-------------------------------------------------------------------------------------------------------------------------
#   
       
if __name__ == "__main__":
    root = tk.Tk()
    radio_panel = Toplevel1(root)

    # Avvio del thread di lettura seriale
    serial_thread = threading.Thread(target=read_from_port, args=(ser,), daemon=True)
    serial_thread.start()

    # Esegui il thread per la gestione dei dati
    processing_thread = threading.Thread(target=process_data, daemon=True)
    processing_thread.start()

    transmission_enabled = True
    root.after(1000, get_frequency)     # Ritardo più lungo per dare tempo alla seriale di stabilizzarsi
    root.after(600, get_squelch)
    root.after(700, get_rfgain)
  
    root.mainloop()
