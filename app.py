import streamlit as st
import json
import os
import re
import pandas as pd
import smtplib
import random
import string
from email.message import EmailMessage
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

# Configurazione pagina
st.set_page_config(page_title="Sielte Rottamazione", layout="wide")

# Costanti SMTP
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = "no.reply.rec.psw@gmail.com"
SMTP_PASSWORD = "usrq vbeu pwap pubp"

UTENTI_FILE = "utenti.json"
DATA_FILE = os.path.join("data", "data.xlsx")

# --- Funzioni Utenti ---
def carica_utenti():
    if os.path.exists(UTENTI_FILE):
        try:
            with open(UTENTI_FILE, 'r') as f:
                contenuto = f.read().strip()
                if not contenuto:
                    return []
                return json.loads(contenuto)
        except json.JSONDecodeError:
            st.warning("⚠️ Il file utenti.json è danneggiato. Verrà sovrascritto.")
            return []
    return []

def salva_utenti(lista_utenti):
    with open(UTENTI_FILE, 'w') as f:
        json.dump(lista_utenti, f, indent=4)

# --- Stile CSS ---
def stile_login():
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(135deg, #2c3e50, #3498db);
            color: white;
        }
        label, div[data-baseweb="radio"] * {
            color: white !important;
            font-weight: bold;
        }
        div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] > p {
            color: white !important;
            font-weight: bold;
        }
        .title-center {
            text-align: center;
            color: white;
            font-size: 2.5em;
            font-weight: bold;
            margin-top: 1em;
            margin-bottom: 0.5em;
        }
        .stButton > button {
            background-color: #00bcd4;
            color: white;
            font-weight: bold;
            border-radius: 8px;
            padding: 0.5em 1.5em;
        }
        .custom-success {
            background-color: #4CAF50;
            padding: 1rem;
            border-radius: 8px;
            color: white;
            font-weight: bold;
        }
                /* Cambia solo il colore del testo del pulsante Scarica CSV */
        [data-testid="stDownloadButton"] button {
            color: black !important;
            font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)
def messaggio_successo(testo):
    st.markdown(f"<div class='custom-success'>✅ {testo}</div>", unsafe_allow_html=True)

# --- Recupero e reset password ---
def genera_password_temporanea(n=10):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choices(chars, k=n))

def invia_email_nuova_password(dest, pwd):
    msg = EmailMessage()
    msg['Subject'] = 'Recupero Password - Sielte App'
    msg['From'] = SMTP_EMAIL
    msg['To'] = dest
    msg.set_content(f"La tua nuova password temporanea è: {pwd}\nTi verrà chiesto di cambiarla al primo accesso.")
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Errore invio email: {e}")
        return False

# Login
def login():
    st.subheader("Login")
    email = st.text_input("Email")
    pwd = st.text_input("Password", type="password")
    if st.button("Accedi"):
        utenti = carica_utenti()
        for u in utenti:
            if u['email']==email and u['password']==pwd:
                if u.get('reset_required'):
                    st.session_state['utente_reset']=u
                    st.session_state['pagina']='Cambio Password'
                    st.rerun()
                else:
                    messaggio_successo(f"Benvenuto {u['nome']} {u['cognome']}")
                    st.session_state['utente']=u
                    st.rerun()
        st.error("Credenziali non valide")
    if st.button("Recupera Password", type="secondary"):
        st.session_state['pagina']='Recupera Password'
        st.rerun()

# Cambio password forzato
def cambio_password_forzato():
    u = st.session_state.get('utente_reset')
    st.subheader("Cambio Password")
    temp = st.text_input("Password temporanea", type="password")
    new1 = st.text_input("Nuova password", type="password")
    new2 = st.text_input("Conferma nuova password", type="password")
    if st.button("Cambia password"):
        if temp!=u['password']:
            st.error("Temp. non corretta")
        elif new1!=new2:
            st.error("Password non combaciano")
        else:
            utenti=carica_utenti()
            for x in utenti:
                if x['email'].lower()==u['email'].lower():
                    x['password']=new1
                    x['reset_required']=False
            salva_utenti(utenti)
            messaggio_successo("Password aggiornata. Effettua login.")
            st.session_state['pagina']='Login'
            st.session_state['utente_reset']=None
            st.rerun()

# Calcolo intervallo
def calcola_intervallo(dt):
    if pd.isna(dt): return 'Nessun Consumo'
    oggi=pd.Timestamp.today()
    d=oggi-dt
    anni=d.days//365; mesi=(d.days%365)//30; giorni=(d.days%365)%30
    if anni>1: return f"{anni} Anni"
    if anni==1: return "1 Anno"
    if mesi>1: return f"{mesi} Mesi"
    if mesi==1: return "1 Mese"
    return "Oggi"

# --- Dashboard principale ---
def mostra_dashboard(utente):
    stile_login()
    st.markdown(f"<div class='title-center'>Benvenuto, {utente['nome']}!</div>", unsafe_allow_html=True)
    st.write(f"Ruolo: **{utente['ruolo']}**")
    current_email=utente['email']
    try:
        df=pd.read_excel(DATA_FILE)
    except Exception as e:
        st.error(f"Errore caricamento Excel: {e}"); return
    df.columns=df.columns.str.strip()
    df=df.reset_index().rename(columns={'index':'_orig_index'})
    for c in ['Dislocazione Territoriale','CodReparto','Ubicazione','Articolo','Descrizione']:
        df[c]=df.get(c,'TRANSITO').fillna('TRANSITO').astype(str).str.replace(r"\.0$","",regex=True)
    df['Giacenza']=pd.to_numeric(df.get('Giacenza',0),errors='coerce').fillna(0).astype(int)
    df['Valore Complessivo']=pd.to_numeric(df.get('Valore Complessivo',0),errors='coerce').fillna(0.0)
    df['Rottamazione']=df.get('Rottamazione',False).fillna(False).astype(bool)
    df['UserRottamazione']=df.get('UserRottamazione','').fillna('').astype(str)
    df['Data Ultimo Carico']=pd.to_datetime(df.get('Data Ultimo Carico',pd.NaT),errors='coerce')
    df['Data Ultimo Consumo']=pd.to_datetime(df.get('Data Ultimo Consumo',pd.NaT),errors='coerce')
    df['Ultimo Consumo']=df['Data Ultimo Consumo'].apply(calcola_intervallo)
    # Filtri
    st.markdown('### Filtri')
    rep_sel=st.multiselect('Filtra per Reparto',df['CodReparto'].unique().tolist())
    dis_sel=st.multiselect('Filtra per Dislocazione Territoriale',df['Dislocazione Territoriale'].unique().tolist())
    ubi_sel=st.multiselect('Filtra per Ubicazione',df['Ubicazione'].unique().tolist())
    vals=df['Ultimo Consumo'].dropna().unique().tolist()
    vals=[v for v in vals if 'Giorno' not in v and v!='Oggi']
    def ord(v):
        if 'Anno' in v: return (0,int(v.split()[0]))
        if 'Mese' in v: return (1,int(v.split()[0]))
        if v=='Nessun Consumo': return (2,0)
        return (99,0)
    vals=sorted(vals,key=ord)
    consumo_sel=st.multiselect('Filtra per Ultimo Consumo',vals)
    dff=df.copy()
    if rep_sel: dff=dff[dff['CodReparto'].isin(rep_sel)]
    if dis_sel: dff=dff[dff['Dislocazione Territoriale'].isin(dis_sel)]
    if ubi_sel: dff=dff[dff['Ubicazione'].isin(ubi_sel)]
    if consumo_sel: dff=dff[dff['Ultimo Consumo'].isin(consumo_sel)]
    # Scarica CSV
    st.download_button('📥 Scarica CSV',dff.to_csv(index=False).encode('utf-8'),file_name='tabella_filtrata.csv')
    # AgGrid
    cols=['_orig_index','Dislocazione Territoriale','CodReparto','Ubicazione','Articolo','Descrizione','Giacenza','Valore Complessivo','Rottamazione','UserRottamazione','Data Ultimo Carico','Data Ultimo Consumo','Ultimo Consumo']
    grid_df=dff[cols].copy()
    grid_df['Valore Complessivo']=grid_df['Valore Complessivo'].map(lambda x:f"€ {x:,.2f}".replace(',', 'X').replace('.', ',').replace('X','.'))
    gb=GridOptionsBuilder.from_dataframe(grid_df)
    gb.configure_column('_orig_index',hide=True)
    gb.configure_column('Rottamazione',editable=True,cellEditor='agCheckboxCellEditor')
    gb.configure_column('UserRottamazione',editable=False)
    opts=gb.build()
    resp=AgGrid(grid_df,gridOptions=opts,fit_columns_on_grid_load=True,update_mode=GridUpdateMode.VALUE_CHANGED,data_return_mode=DataReturnMode.FILTERED_AND_SORTED)
    upd=resp['data']
    if isinstance(upd,pd.DataFrame): upd=upd.to_dict('records')
    if st.button('Salva'):
        df2=pd.read_excel(DATA_FILE)
        df2.columns=df2.columns.str.strip()
        for c in ['CodReparto','Dislocazione Territoriale','Ubicazione']:
            df2[c]=df2[c].astype(str).str.replace(r"\.0$","",regex=True)
        df2['Rottamazione']=df2.get('Rottamazione',False).fillna(False).astype(bool)
        df2['UserRottamazione']=df2.get('UserRottamazione','').fillna('').astype(str)
        blocked=0
        for row in upd:
            i=int(row['_orig_index'])
            flag=bool(row['Rottamazione'])
            prev=df2.at[i,'UserRottamazione']
            if flag and not prev:
                df2.at[i,'Rottamazione']=True; df2.at[i,'UserRottamazione']=current_email
            elif not flag and prev==current_email:
                df2.at[i,'Rottamazione']=False; df2.at[i,'UserRottamazione']=''
            elif prev and prev!=current_email:
                blocked+=1
        df2.to_excel(DATA_FILE,index=False)
        st.markdown('<script>window.onbeforeunload=null;</script>',unsafe_allow_html=True)
        messaggio_successo(f"✅ Modifiche salvate. Righe non modificate: {blocked}")
        st.rerun()
    # Statistiche
    st.markdown(f"**Totale articoli filtrati:** {len(dff)}")
    st.markdown(f"**Articoli da rottamare:** {dff['Rottamazione'].sum()}")

# Interfaccia logo
def interfaccia():
    col1,col2=st.columns([1,5])
    with col1:
        try: st.image("https://.../logo.png",width=180)
        except: st.markdown("🧭")
    with col2:
        st.markdown('<div class="title-center">Login</div>',unsafe_allow_html=True)

# Main
def main():
    stile_login()
    if 'pagina' not in st.session_state: st.session_state['pagina']='Login'
    if 'utente' not in st.session_state: st.session_state['utente']=None
    if st.session_state.get('registrazione_completata'):
        messaggio_successo("Registrazione completata..."); st.experimental_rerun()
    if st.session_state.get('utente_reset'):
        cambio_password_forzato(); return
    if st.session_state['utente']:
        mostra_dashboard(st.session_state['utente']); return
    interfaccia()
    pagine=['Login','Registrazione','Recupera Password']
    pag=st.radio('Navigazione',pagine,index=pagine.index(st.session_state['pagina']))
    if pag=='Login': login()
    elif pag=='Registrazione': pass  # implementa registrazione
    elif pag=='Recupera Password': recupera_password()

if __name__=='__main__': main()








