import streamlit as st
import json
import os
import pandas as pd
import smtplib
import random
import string
from email.message import EmailMessage
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

# --- Funzioni di supporto ---
def calcola_intervallo(dt):
    if pd.isna(dt): return "Nessun Consumo"
    delta = pd.Timestamp.today() - dt
    anni  = delta.days // 365
    mesi  = (delta.days % 365) // 30
    if anni > 1: return f"{anni} Anni"
    if anni == 1: return "1 Anno"
    if mesi > 1: return f"{mesi} Mesi"
    if mesi == 1: return "1 Mese"
    return "Oggi"

def key_consumo(v):
    if v.startswith("Nessun"): return (2, 0)
    parts = v.split(); num = int(parts[0]) if parts and parts[0].isdigit() else 0
    if "Mese" in v: return (0, num)
    if "Anno" in v: return (1, num)
    return (3, num)

# Configurazione pagina
st.set_page_config(page_title="Sielte Rottamazione", layout="wide")

# Costanti
SMTP_SERVER   = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_EMAIL    = "no.reply.rec.psw@gmail.com"
SMTP_PASSWORD = "usrq vbeu pwap pubp"
UTENTI_FILE   = "utenti.json"
DATA_FILE     = os.path.join("data", "data.xlsx")

# --- Utility utenti ---
def carica_utenti():
    if os.path.exists(UTENTI_FILE):
        try:
            text = open(UTENTI_FILE).read().strip()
            return json.loads(text) if text else []
        except json.JSONDecodeError:
            st.warning("⚠️ utenti.json danneggiato, verrà ricreato.")
    return []

def salva_utenti(users):
    with open(UTENTI_FILE, 'w') as f: json.dump(users, f, indent=4)

# --- Styling ---
def stile_login():
    st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg,#2c3e50,#3498db); color:white; }
    .title-center { text-align:center; color:white; font-size:2.5em; margin:1em 0; }
    .stButton>button { background:#00bcd4; color:white; font-weight:bold; border-radius:8px; }
    .custom-success { background:#4caf50; padding:1rem; border-radius:8px; color:white; }
    </style>
    """, unsafe_allow_html=True)

def messaggio_successo(texto):
    st.markdown(f"<div class='custom-success'>✅ {texto}</div>", unsafe_allow_html=True)

# --- Lettura dati con cache ---
@st.cache_data(ttl=3600)
def load_and_prepare_data():
    df = pd.read_excel(DATA_FILE, engine="openpyxl")
    df.columns = df.columns.str.strip()
    df['Rottamazione'] = df.get('Rottamazione', False).fillna(False).astype(bool)
    df['UserRottamazione'] = df.get('UserRottamazione', '').fillna('').astype(str)
    df_proc = df.reset_index().rename(columns={'index':'_orig_index'})
    for c in ['Dislocazione Territoriale','CodReparto','Ubicazione','Articolo','Descrizione']:
        df_proc[c] = df_proc[c].fillna('TRANSITO').astype(str).str.replace(r'\.0$','',regex=True)
    df_proc['Giacenza'] = pd.to_numeric(df_proc.get('Giacenza',0),errors='coerce').fillna(0).astype(int)
    df_proc['Valore Complessivo'] = pd.to_numeric(df_proc.get('Valore Complessivo',0),errors='coerce').fillna(0.)
    df_proc['Data Ultimo Carico'] = pd.to_datetime(df['Data Ultimo Carico'],errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')
    df_proc['Data Ultimo Consumo'] = pd.to_datetime(df['Data Ultimo Consumo'],errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')
    df_proc['Ultimo Consumo'] = pd.to_datetime(df['Data Ultimo Consumo'],errors='coerce').apply(calcola_intervallo)
    return df, df_proc

# --- Funzioni pagina Save ---
def save_page():
    stile_login()
    st.subheader("Salvataggio in corso...")
    df_raw = st.session_state['df_raw']
    updated = st.session_state['to_save']
    current_email = st.session_state['utente']['email']
    df2 = df_raw.copy(); blocked=0
    for row in updated:
        idx = int(row['_orig_index']); newf = bool(row['Rottamazione']); prev = df2.at[idx,'UserRottamazione']
        if newf and not prev:
            df2.at[idx,'Rottamazione']=True; df2.at[idx,'UserRottamazione']=current_email
        elif not newf and prev==current_email:
            df2.at[idx,'Rottamazione']=False; df2.at[idx,'UserRottamazione']=''
        elif prev and prev!=current_email:
            blocked+=1
    df2.to_excel(DATA_FILE,index=False,engine='openpyxl')
    messaggio_successo(f"✅ Salvataggio completato! Righe non modificate: {blocked}")
    # redirect a login
    st.query_params['page'] = ['login']

# --- Login / Registrazione / Reset Password ---
def login_page():
    stile_login()
    st.subheader('Login')
    email = st.text_input('Email')
    pwd = st.text_input('Password', type='password')
    c1, c2 = st.columns(2)
    with c1:
        if st.button('Accedi'):
            for u in carica_utenti():
                if u['email'] == email and u['password'] == pwd:
                    if u.get('reset_required'):
                        st.session_state['utente_reset'] = u
                        st.query_params['page'] = ['reset']
                    else:
                        st.session_state['utente'] = u
                        st.query_params['page'] = ['dashboard']
                    return
            st.error('Credenziali non valide')
    with c2:
        if st.button('Registrati'):
            st.query_params['page'] = ['registrazione']
        if st.button('Recupera Password'):
            st.query_params['page'] = ['reset']

# placeholder per registrazione, reset...
def registrazione_page():
    stile_login()
    st.subheader('Registrazione')
    # qui la logica di registrazione

def reset_page():
    stile_login()
    st.subheader('Recupera Password')
    # qui la logica di reset password...
def registrazione_page(): st.write('Registrazione')
def reset_page(): st.write('Reset Password')

# --- Dashboard principale ---
def dashboard_page():
    stile_login(); ut=st.session_state['utente']; st.markdown(f"<div class='title-center'>Benvenuto {ut['nome']} {ut['cognome']}</div>",unsafe_allow_html=True)
    df_raw, df = load_and_prepare_data()
    st.session_state['df_raw']=df_raw
    # Filtri e tabella (come prima)
    st.markdown('### Filtri')
    rep_sel=st.multiselect('Reparto',df['CodReparto'].unique());dis_sel=st.multiselect('Territoriale',df['Dislocazione Territoriale'].unique())
    ubi_sel=st.multiselect('Ubicazione',df['Ubicazione'].unique()); vals=sorted(df['Ultimo Consumo'].unique(),key=key_consumo)
    consumo_sel=st.multiselect('Consumo',vals)
    dff=df.copy();
    if rep_sel: dff=dff[dff['CodReparto'].isin(rep_sel)]
    if dis_sel: dff=dff[dff['Dislocazione Territoriale'].isin(dis_sel)]
    if ubi_sel: dff=dff[dff['Ubicazione'].isin(ubi_sel)]
    if consumo_sel: dff=dff[dff['Ultimo Consumo'].isin(consumo_sel)]
    st.download_button('📥 Scarica CSV',data=dff.to_csv(index=False).encode('utf-8'),mime='text/csv')
    cols=['_orig_index','Dislocazione Territoriale','CodReparto','Ubicazione','Articolo','Descrizione','Giacenza','Valore Complessivo','Rottamazione','UserRottamazione','Data Ultimo Carico','Data Ultimo Consumo','Ultimo Consumo']
    grid_df=dff[cols].copy()
    gb=GridOptionsBuilder.from_dataframe(grid_df)
    gb.configure_column('_orig_index',hide=True); gb.configure_column('Rottamazione',editable=True,cellEditor='agCheckboxCellEditor')
    gb.configure_column('UserRottamazione',editable=False)
    resp=AgGrid(grid_df,gridOptions=gb.build(),fit_columns_on_grid_load=True,update_mode=GridUpdateMode.MODEL_CHANGED,data_return_mode=DataReturnMode.FILTERED_AND_SORTED)
    updated = resp['data'] if not hasattr(resp['data'],'to_dict') else resp['data'].to_dict('records')
    st.session_state['to_save']=updated
    if st.button('Salva'):
        # Mostra subito messaggio di attesa
        st.info('⏳ Attendere: salvataggio in corso...')
        # Naviga alla pagina di salvataggio
        st.query_params['page'] = ['save']

# --- Router ---
def main():
    params = st.query_params
    page = params.get('page',['login'])[0]
    if page=='login': login_page()
    elif page=='dashboard': dashboard_page()
    elif page=='save': save_page()
    elif page=='registrazione': registrazione_page()
    elif page=='reset': reset_page()
    else: login_page()

if __name__=='__main__': main()




