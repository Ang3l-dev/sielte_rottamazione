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

# --- Styling ---
# CSS
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
    st.markdown(f"""<div class='custom-success'>✅ {testo}</div>""", unsafe_allow_html=True)

# Login
def login():
    st.subheader("Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Accedi"):
        utenti = carica_utenti()
        for utente in utenti:
            if utente["email"] == email and utente["password"] == password:
                if utente.get("reset_required"):
                    st.session_state["utente_reset"] = utente
                    st.session_state["pagina"] = "Cambio Password"
                    st.rerun()
                else:
                    messaggio_successo(f"Benvenuto {utente['nome']} {utente['cognome']}")
                    st.session_state["utente"] = utente
                    st.rerun()
        st.error("Credenziali non valide")

    if st.button("Recupera Password", type="secondary"):
        st.session_state["pagina"] = "Recupera Password"
        st.rerun()

# Registrazione
@st.cache_data
def carica_reparti_da_excel():
    try:
        df = pd.read_excel(DATA_FILE)
        df["CodReparto"] = df["CodReparto"].fillna("").astype(str)
        return sorted(df["CodReparto"].unique())
    except Exception as e:
        st.error(f"Errore caricamento Reparti: {e}")
        return []

def registrazione():
    st.markdown('<div class="title-center">Registrazione</div>', unsafe_allow_html=True)
    nome = st.text_input("Nome")
    cognome = st.text_input("Cognome")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    conferma_password = st.text_input("Conferma Password", type="password")
    st.caption("🔐 La password deve contenere almeno 6 caratteri, un numero e un simbolo.")

    ruolo = st.radio("Ruolo", ["User"])
    if ruolo == "User":
        reparti_disponibili = carica_reparti_da_excel()
        reparti = st.multiselect("Reparti abilitati", reparti_disponibili)
    else:
        reparti = []


    if st.button("Registra"):
        errori = []

        if not nome.strip(): errori.append("Nome mancante")
        if not cognome.strip(): errori.append("Cognome mancante")
        if not email.strip(): errori.append("Email mancante")
        if not password.strip(): errori.append("Password mancante")
        if not conferma_password.strip(): errori.append("Conferma Password mancante")
        if password != conferma_password: errori.append("Le password non corrispondono")
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email): errori.append("Formato email non valido")
        if len(password) < 6 or not re.search(r"\d", password) or not re.search(r"[^\w\s]", password):
            errori.append("Password non conforme ai criteri")
        if ruolo == "User" and not reparti: errori.append("Seleziona almeno un reparto")

        utenti = carica_utenti()
        if any(u["email"].lower() == email.lower() for u in utenti):
            errori.append("⚠️ Questo indirizzo email è già registrato.")

        if errori:
            for e in errori:
                st.error(f"❌ {e}")
            return

        nuovo_utente = {
            "nome": nome,
            "cognome": cognome,
            "email": email,
            "password": password,
            "ruolo": ruolo,
            "reparti": reparti if ruolo == "User" else "ALL",
            "reset_required": False
        }

        utenti.append(nuovo_utente)
        salva_utenti(utenti)
        st.session_state["registrazione_completata"] = True
        st.session_state["pagina"] = "Login"
        st.rerun()

# Recupero password
def recupera_password():
    st.markdown('<div class="title-center">Recupera Password</div>', unsafe_allow_html=True)
    email = st.text_input("Inserisci il tuo indirizzo email")

    if st.button("Invia nuova password"):
        st.info("📤 Invio in corso...")
        utenti = carica_utenti()
        utente = next((u for u in utenti if u["email"].lower() == email.lower()), None)

        if utente:
            nuova_password = genera_password_temporanea()
            utente["password"] = nuova_password
            utente["reset_required"] = True
            salva_utenti(utenti)

            if invia_email_nuova_password(email, nuova_password):
                st.success("✅ Email inviata con la nuova password. Controlla la tua casella.")
                # Attesa per far leggere il messaggio
                time_script = """
                    <script>
                        setTimeout(function() {
                            window.location.reload();
                        }, 3000);
                    </script>
                """
                st.markdown(time_script, unsafe_allow_html=True)
                st.stop()
        else:
            st.error("⚠️ Indirizzo email non trovato.")


# Cambio password obbligatorio dopo reset
def cambio_password_forzato():
    utente = st.session_state.get("utente_reset")
    st.markdown('<div class="title-center">Cambio Password</div>', unsafe_allow_html=True)

    pwd_temp = st.text_input("Reinserisci la password temporanea", type="password")
    nuova_pwd = st.text_input("Nuova password", type="password")
    conferma_pwd = st.text_input("Conferma nuova password", type="password")

    if st.button("Cambia password"):
        if pwd_temp != utente["password"]:
            st.error("❌ La password temporanea non è corretta.")
            return
        if nuova_pwd != conferma_pwd:
            st.error("❌ Le nuove password non corrispondono.")
            return
        if len(nuova_pwd) < 6 or not re.search(r"\d", nuova_pwd) or not re.search(r"[^\w\s]", nuova_pwd):
            st.error("❌ La nuova password non è conforme ai criteri.")
            return

        utenti = carica_utenti()
        for u in utenti:
            if u["email"].lower() == utente["email"].lower():
                u["password"] = nuova_pwd
                u["reset_required"] = False
                break
        salva_utenti(utenti)

        messaggio_successo("Password aggiornata. Puoi effettuare il login.")
        st.session_state["pagina"] = "Login"
        st.session_state["utente_reset"] = None
        st.rerun()
#CALCOLO INTERVALLO DATA
def calcola_intervallo(dt):
    if pd.isna(dt) or str(dt).strip() == '-':
        return "Nessun Consumo"
    oggi = pd.Timestamp.today()
    delta = oggi - dt
    anni = delta.days // 365
    mesi = (delta.days % 365) // 30
    giorni = (delta.days % 365) % 30

    if anni >= 2:
        return f"{anni} Anni"
    elif anni == 1:
        return "1 Anno"
    elif mesi >= 2:
        return f"{mesi} Mesi"
    elif mesi == 1:
        return "1 Mese"
    else:
        return "Oggi"  # Al posto di Giorni, così da non finire nel filtro



# --- Dashboard principale ---
def mostra_dashboard(utente):
    stile_login()
    st.markdown(f"<div class='title-center'>Benvenuto, {utente['nome']}!</div>", unsafe_allow_html=True)
    st.write(f"Ruolo: **{utente['ruolo']}**")
    current_email = utente['email']

    try:
        df = pd.read_excel(DATA_FILE)
    except Exception as e:
        st.error(f"Errore caricamento Excel: {e}")
        return

    df.columns = df.columns.str.strip()
    df = df.reset_index().rename(columns={'index': '_orig_index'})

    for c in ['Dislocazione Territoriale','CodReparto','Ubicazione','Articolo','Descrizione']:
        df[c] = df.get(c, 'TRANSITO').fillna('TRANSITO').astype(str).str.replace(r"\.0$", "", regex=True)

    df['Giacenza'] = pd.to_numeric(df.get('Giacenza', 0), errors='coerce').fillna(0).astype(int)
    df['Valore Complessivo'] = pd.to_numeric(df.get('Valore Complessivo', 0), errors='coerce').fillna(0.0)
    df['Rottamazione'] = df.get('Rottamazione', False).fillna(False).astype(bool)
    df['UserRottamazione'] = df.get('UserRottamazione', '').fillna('').astype(str)
    
    df['Data Ultimo Carico'] = pd.to_datetime(df.get('Data Ultimo Carico', pd.NaT), errors='coerce').dt.strftime('%d/%m/%Y')
    df['Data Ultimo Consumo'] = pd.to_datetime(df.get('Data Ultimo Consumo', pd.NaT), errors='coerce').dt.strftime('%d/%m/%Y')
    df['Ultimo Consumo'] = pd.to_datetime(df['Data Ultimo Consumo'], errors='coerce').apply(calcola_intervallo)


    # --- FILTRI ---
    st.markdown('### Filtri')
    rep_sel = st.multiselect('Filtra per Reparto', df['CodReparto'].unique().tolist())
    dis_sel = st.multiselect('Filtra per Dislocazione Territoriale', df['Dislocazione Territoriale'].unique().tolist())
    ubi_sel = st.multiselect('Filtra per Ubicazione', df['Ubicazione'].unique().tolist())

    # Rimuovi intervalli in giorni dal filtro
    intervalli_validi = sorted(set(i for i in df['Ultimo Consumo'].unique()
                                   if i not in ["Oggi", "1 Giorno", "2 Giorni", "3 Giorni", "Nessun Consumo"]
                                   and ("Mese" in i or "Anno" in i)),
                               key=lambda x: (
                                   int(x.split()[0]) if x.split()[0].isdigit() else 0,
                                   0 if "Mese" in x else 1  # Prima i mesi poi gli anni
                               ))
    consumo_sel = st.multiselect('Filtra per Ultimo Consumo (solo mesi/anni)', intervalli_validi)

    dff = df.copy()
    if rep_sel: dff = dff[dff['CodReparto'].isin(rep_sel)]
    if dis_sel: dff = dff[dff['Dislocazione Territoriale'].isin(dis_sel)]
    if ubi_sel: dff = dff[dff['Ubicazione'].isin(ubi_sel)]
    if consumo_sel: dff = dff[dff['Ultimo Consumo'].isin(consumo_sel)]

    st.download_button("📥 Scarica CSV", dff.to_csv(index=False).encode("utf-8"), file_name="tabella_filtrata.csv")

    cols = ['_orig_index','Dislocazione Territoriale','CodReparto','Ubicazione','Articolo',
            'Descrizione','Giacenza','Valore Complessivo','Rottamazione','UserRottamazione',
            'Data Ultimo Carico','Data Ultimo Consumo','Ultimo Consumo']
    
    grid_df = dff[cols].copy()
    grid_df['Valore Complessivo'] = grid_df['Valore Complessivo'].map(lambda x: f"€ {x:,.2f}".replace(',', 'X').replace('.', ',').replace('X','.'))

    gb = GridOptionsBuilder.from_dataframe(grid_df)
    gb.configure_column('_orig_index', header_name="", hide=True, suppressColumnsToolPanel=True)
    gb.configure_column('Rottamazione', editable=True, cellEditor='agCheckboxCellEditor')
    gb.configure_column('UserRottamazione', editable=False)
    grid_opts = gb.build()

    response = AgGrid(grid_df, gridOptions=grid_opts, fit_columns_on_grid_load=True,
                      update_mode=GridUpdateMode.VALUE_CHANGED, data_return_mode=DataReturnMode.FILTERED_AND_SORTED)

    updated = response['data'].to_dict('records') if isinstance(response['data'], pd.DataFrame) else []

    if st.button('Salva'):
        df2 = pd.read_excel(DATA_FILE)
        df2.columns = df2.columns.str.strip()
        for c in ['CodReparto','Dislocazione Territoriale','Ubicazione']:
            df2[c] = df2[c].astype(str).str.replace(r"\.0$", "", regex=True)
        df2['Rottamazione'] = df2.get('Rottamazione', False).fillna(False).astype(bool)
        df2['UserRottamazione'] = df2.get('UserRottamazione', '').fillna('').astype(str)
        modifiche_bloccate = 0
        for row in updated:
            idx = int(row['_orig_index'])
            new_flag = bool(row['Rottamazione'])
            prev_user = df2.at[idx, 'UserRottamazione']
            if new_flag and not prev_user:
                df2.at[idx, 'Rottamazione'] = True
                df2.at[idx, 'UserRottamazione'] = current_email
            elif not new_flag and prev_user == current_email:
                df2.at[idx, 'Rottamazione'] = False
                df2.at[idx, 'UserRottamazione'] = ''
            elif prev_user and prev_user != current_email:
                modifiche_bloccate += 1
        df2.to_excel(DATA_FILE, index=False)
        st.markdown('<script>window.onbeforeunload=null;</script>', unsafe_allow_html=True)
        messaggio_successo(f'✅ Modifiche salvate. Righe non modificate per permessi: {modifiche_bloccate}')
        st.rerun()

    st.markdown(f"**Totale articoli filtrati:** {len(dff)}")
    st.markdown(f"**Articoli da rottamare:** {dff['Rottamazione'].sum()}")



# Interfaccia logo
def interfaccia():
    col1, col2 = st.columns([1, 5])
    with col1:
        try:
            st.image("https://www.confindustriaemilia.it/flex/AppData/Redational/ElencoAssociati/0.11906600%201536649262/e037179fa82dad8532a1077ee51a4613.png", width=180)
        except:
            st.markdown("🧭")
    with col2:
        st.markdown('<div class="title-center">Login</div>', unsafe_allow_html=True)

# Main
def main():
    stile_login()

    if "pagina" not in st.session_state:
        st.session_state["pagina"] = "Login"
    if "utente" not in st.session_state:
        st.session_state["utente"] = None

    if st.session_state.get("registrazione_completata"):
        messaggio_successo("Registrazione completata. Verrai reindirizzato alla schermata di login.")
        st.markdown("""
            <meta http-equiv="refresh" content="2">
            <script>
                setTimeout(function() {
                    window.location.reload();
                }, 2000);
            </script>
        """, unsafe_allow_html=True)
        st.stop()

    if st.session_state.get("utente_reset"):
        cambio_password_forzato()
        return

    if st.session_state["utente"]:
        mostra_dashboard(st.session_state["utente"])
        return

    interfaccia()
    pagine = ["Login", "Registrazione", "Recupera Password"]
    pagina = st.radio("Navigazione", pagine, index=pagine.index(st.session_state.get("pagina", "Login")))

    if pagina == "Login":
        login()
    elif pagina == "Registrazione":
        registrazione()
    elif pagina == "Recupera Password":
        recupera_password()

if __name__ == "__main__":
    main()









