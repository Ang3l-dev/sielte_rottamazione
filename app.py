import streamlit as st
import json
import os
import pandas as pd
import smtplib
import random
import string
import threading
from email.message import EmailMessage
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Union

# --- Costanti e configurazioni ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = "no.reply.rec.psw@gmail.com"
SMTP_PASSWORD = "usrq vbeu pwap pubp"
UTENTI_FILE = "utenti.json"
DATA_FILE = os.path.join("data", "data.xlsx")
SESSION_TIMEOUT = 1800  # 30 minuti in secondi

# --- Tipi di dati ---
UserDict = Dict[str, Union[str, bool]]
DataFrame = pd.DataFrame

# --- Funzioni di supporto ---
def calcola_intervallo(dt: pd.Timestamp) -> str:
    """Calcola l'intervallo di tempo dalla data specificata a oggi."""
    if pd.isna(dt):
        return "Nessun Consumo"
    
    delta = pd.Timestamp.today() - dt
    anni = delta.days // 365
    mesi = (delta.days % 365) // 30
    
    if anni > 1:
        return f"{anni} Anni"
    if anni == 1:
        return "1 Anno"
    if mesi > 1:
        return f"{mesi} Mesi"
    if mesi == 1:
        return "1 Mese"
    return "Oggi"

def key_consumo(v: str) -> Tuple[int, int]:
    """Funzione chiave per ordinare gli intervalli di consumo."""
    if v.startswith("Nessun"):
        return (2, 0)
    
    parts = v.split()
    num = int(parts[0]) if parts and parts[0].isdigit() else 0
    
    if "Mese" in v:
        return (0, num)
    if "Anno" in v:
        return (1, num)
    return (3, num)

def verifica_sessione() -> bool:
    """Verifica se la sessione è scaduta."""
    if "last_activity" not in st.session_state:
        return False
    
    tempo_trascorso = datetime.now() - st.session_state["last_activity"]
    return tempo_trascorso.total_seconds() < SESSION_TIMEOUT

def aggiorna_attivita():
    """Aggiorna il timestamp dell'ultima attività."""
    st.session_state["last_activity"] = datetime.now()

# --- Gestione utenti ---
def carica_utenti() -> List[UserDict]:
    """Carica la lista degli utenti dal file JSON."""
    if not os.path.exists(UTENTI_FILE):
        return []
    
    try:
        with open(UTENTI_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError) as e:
        st.error(f"Errore nel caricamento degli utenti: {str(e)}")
        return []

def salva_utenti(users: List[UserDict]) -> bool:
    """Salva la lista degli utenti nel file JSON."""
    try:
        with open(UTENTI_FILE, "w") as f:
            json.dump(users, f, indent=4)
        return True
    except (IOError, TypeError) as e:
        st.error(f"Errore nel salvataggio degli utenti: {str(e)}")
        return False

def trova_utente(email: str) -> Optional[UserDict]:
    """Trova un utente per email."""
    users = carica_utenti()
    for user in users:
        if user["email"] == email:
            return user
    return None

# --- Gestione password ---
def genera_password_temporanea(n: int = 12) -> str:
    """Genera una password temporanea sicura."""
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(random.choices(chars, k=n))

def invia_email(destinatario: str, oggetto: str, corpo: str) -> bool:
    """Invia un'email usando SMTP."""
    msg = EmailMessage()
    msg["Subject"] = oggetto
    msg["From"] = SMTP_EMAIL
    msg["To"] = destinatario
    msg.set_content(corpo)
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Errore nell'invio dell'email: {str(e)}")
        return False

def invia_email_nuova_password(destinatario: str, password: str) -> bool:
    """Invia l'email con la nuova password temporanea."""
    oggetto = "Recupero Password - Sielte App"
    corpo = f"""La tua nuova password temporanea è: {password}
    
Ti verrà chiesto di cambiarla al primo accesso.
    
Per motivi di sicurezza, non condividere questa password con nessuno.
    
Se non hai richiesto questo reset, ti preghiamo di contattare l'amministratore."""
    
    return invia_email(destinatario, oggetto, corpo)

# --- Gestione dati ---
@st.cache_data(ttl=3600)
def load_and_prepare_data() -> Tuple[DataFrame, DataFrame]:
    """Carica e prepara i dati dall'Excel."""
    try:
        df = pd.read_excel(DATA_FILE, engine="openpyxl")
    except Exception as e:
        st.error(f"Errore nel caricamento del file dati: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()
    
    # Pulizia colonne
    df.columns = df.columns.str.strip()
    
    # Gestione valori mancanti
    df["Rottamazione"] = df.get("Rottamazione", False).fillna(False).astype(bool)
    df["UserRottamazione"] = df.get("UserRottamazione", "").fillna("").astype(str)
    
    # Creazione dataframe processato
    df_proc = df.reset_index().rename(columns={"index": "_orig_index"})
    
    # Pulizia colonne specifiche
    text_cols = ["Dislocazione Territoriale", "CodReparto", "Ubicazione", "Articolo", "Descrizione"]
    for col in text_cols:
        df_proc[col] = df_proc[col].fillna("TRANSITO").astype(str).str.replace(r"\.0$", "", regex=True)
    
    # Conversione tipi di dati
    df_proc["Giacenza"] = pd.to_numeric(df_proc.get("Giacenza", 0), errors="coerce").fillna(0).astype(int)
    df_proc["Valore Complessivo"] = pd.to_numeric(df_proc.get("Valore Complessivo", 0), errors="coerce").fillna(0.0)
    
    # Formattazione date
    df_proc["Data Ultimo Carico"] = pd.to_datetime(df["Data Ultimo Carico"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("-")
    df_proc["Data Ultimo Consumo"] = pd.to_datetime(df["Data Ultimo Consumo"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("-")
    df_proc["Ultimo Consumo"] = pd.to_datetime(df["Data Ultimo Consumo"], errors="coerce").apply(calcola_intervallo)
    
    return df, df_proc

def salva_dati(df: DataFrame) -> bool:
    """Salva i dati nel file Excel."""
    try:
        df.to_excel(DATA_FILE, index=False, engine="openpyxl")
        return True
    except Exception as e:
        st.error(f"Errore nel salvataggio dei dati: {str(e)}")
        return False

# --- Funzioni di salvataggio in background ---
def background_save_logic(updated_data: List[Dict], df_raw: DataFrame, current_email: str) -> int:
    """Logica di salvataggio eseguita in background."""
    blocked = 0
    df = df_raw.copy()
    
    for row in updated_data:
        idx = int(row["_orig_index"])
        new_flag = bool(row["Rottamazione"])
        prev_user = df.at[idx, "UserRottamazione"]
        
        if new_flag and not prev_user:
            df.at[idx, "Rottamazione"] = True
            df.at[idx, "UserRottamazione"] = current_email
        elif not new_flag and prev_user == current_email:
            df.at[idx, "Rottamazione"] = False
            df.at[idx, "UserRottamazione"] = ""
        elif prev_user and prev_user != current_email:
            blocked += 1
    
    salva_dati(df)
    return blocked

def background_save(updated_data: List[Dict], df_raw: DataFrame, current_email: str):
    """Avvia il salvataggio in background."""
    def save_and_redirect():
        blocked = background_save_logic(updated_data, df_raw, current_email)
        st.session_state["salvataggio_bloccati"] = blocked
        st.session_state.clear()
        st.session_state["pagina"] = "Login"
    
    thread = threading.Thread(target=save_and_redirect)
    thread.start()
    
    st.success("✅ Salvataggio avviato! Verrai reindirizzato al login.")
    st.markdown("<meta http-equiv='refresh' content='2;url=/' />", unsafe_allow_html=True)
    st.stop()

# --- Interfacce utente ---
def stile_app():
    """Applica lo stile CSS all'applicazione."""
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
    .title-center { 
        text-align: center; 
        color: white; 
        font-size: 2.5em; 
        font-weight: bold; 
        margin: 1em 0; 
    }
        /* Stile specifico per il pulsante Accedi */
    .stForm button[type="submit"] {
        background-color: #00bcd4 !important;
        color: white !important;
        font-weight: bold !important;
    }

    .stButton > button { 
        background-color: #00bcd4; 
        color: white; 
        font-weight: bold; 
        border-radius: 8px; 
        border: none;
        padding: 0.5rem 1rem;
    }
    .stButton > button:hover { 
        background-color: #0097a7; 
    }
    .custom-success { 
        background-color: #4CAF50; 
        padding: 1rem; 
        border-radius: 8px; 
        color: white; 
        margin: 1rem 0;
    }
    .custom-warning { 
        background-color: #FFC107; 
        padding: 1rem; 
        border-radius: 8px; 
        color: black; 
        margin: 1rem 0;
    }
    .custom-error { 
        background-color: #F44336; 
        padding: 1rem; 
        border-radius: 8px; 
        color: white; 
        margin: 1rem 0;
    }
    [data-testid="stDownloadButton"] button { 
        color: black !important; 
        font-weight: bold; 
    }
    .stTextInput input, .stTextInput input:focus {
        background-color: white;
        color: black;
    }
    .stPasswordInput input, .stPasswordInput input:focus {
        background-color: white;
        color: black;
    }
    </style>
    """, unsafe_allow_html=True)

def messaggio_stato(tipo: str, testo: str):
    """Mostra un messaggio di stato stilizzato."""
    class_map = {
        "successo": "custom-success",
        "errore": "custom-error",
        "avviso": "custom-warning"
    }
    icon_map = {
        "successo": "✅",
        "errore": "❌",
        "avviso": "⚠️"
    }
    st.markdown(
        f'<div class="{class_map[tipo]}">{icon_map[tipo]} {testo}</div>', 
        unsafe_allow_html=True
    )

def mostra_intestazione(pagina: str = "Login"):
    """Mostra l'intestazione con logo e titolo."""
    col1, col2 = st.columns([1, 5])
    with col1:
        try:
            st.image(
                "https://www.confindustriaemilia.it/flex/AppData/Redational/ElencoAssociati/0.11906600%201536649262/e037179fa82dad8532a1077ee51a4613.png",
                width=180
            )
        except:
            st.markdown("🧭")
    with col2:
        st.markdown(f'<div class="title-center">{pagina}</div>', unsafe_allow_html=True)

# --- Pagine dell'applicazione ---
def pagina_login():
    """Pagina di login."""
    mostra_intestazione("Login")
    
    with st.form("login_form"):
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        submit = st.form_submit_button("Accedi")
        
        if submit:
            # Converti email in minuscolo per uniformità
            email = email.lower().strip()
            user = trova_utente(email)
            if user and user["password"] == password:
                if user.get("reset_required", False):
                    st.session_state["utente_reset"] = user
                    st.session_state["pagina"] = "Cambio Password"
                else:
                    messaggio_stato("successo", f"Benvenuto {user['nome']} {user['cognome']}")
                    st.session_state["utente"] = user
                    aggiorna_attivita()
                st.rerun()
            else:
                messaggio_stato("errore", "Credenziali non valide")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Registrazione"):
            st.session_state["pagina"] = "Registrazione"
            st.rerun()
    with col2:
        if st.button("Recupera Password"):
            st.session_state["pagina"] = "Recupera Password"
            st.rerun()

def pagina_registrazione():
    """Pagina di registrazione nuovo utente."""
    mostra_intestazione("Registrazione")
    
    with st.form("registrazione_form"):
        nome = st.text_input("Nome", key="reg_nome")
        cognome = st.text_input("Cognome", key="reg_cognome")
        email = st.text_input("Email", key="reg_email")
        ruolo = st.selectbox(
            "Ruolo",
            ["Operatore", "Supervisore", "Amministratore"],
            key="reg_ruolo"
        )
        password = st.text_input("Password", type="password", key="reg_password")
        conferma_password = st.text_input("Conferma Password", type="password", key="reg_conf_password")
        submit = st.form_submit_button("Registrati")
        
        if submit:
            if not all([nome, cognome, email, password, conferma_password]):
                messaggio_stato("errore", "Tutti i campi sono obbligatori")
            elif password != conferma_password:
                messaggio_stato("errore", "Le password non coincidono")
            elif trova_utente(email):
                messaggio_stato("errore", "Email già registrata")
            else:
                nuovo_utente = {
                    "nome": nome.strip(),
                    "cognome": cognome.strip(),
                    "email": email.lower().strip(),
                    "password": password,
                    "ruolo": ruolo,
                    "reset_required": False
                }
                
                users = carica_utenti()
                users.append(nuovo_utente)
                
                if salva_utenti(users):
                    messaggio_stato("successo", "Registrazione completata con successo!")
                    st.session_state["pagina"] = "Login"
                    st.rerun()
                else:
                    messaggio_stato("errore", "Errore nel salvataggio della registrazione")

    if st.button("← Torna al Login"):
        st.session_state["pagina"] = "Login"
        st.rerun()

def pagina_recupera_password():
    """Pagina per il recupero della password."""
    mostra_intestazione("Recupera Password")
    
    with st.form("recupero_form"):
        email = st.text_input("Email registrata", key="rec_email")
        submit = st.form_submit_button("Invia Nuova Password")
        
        if submit:
            user = trova_utente(email)
            if user:
                temp_password = genera_password_temporanea()
                user["password"] = temp_password
                user["reset_required"] = True
                
                users = carica_utenti()
                for i, u in enumerate(users):
                    if u["email"] == email:
                        users[i] = user
                        break
                
                if salva_utenti(users) and invia_email_nuova_password(email, temp_password):
                    messaggio_stato("successo", "Nuova password inviata via email!")
                    st.session_state["pagina"] = "Login"
                    st.rerun()
                else:
                    messaggio_stato("errore", "Errore nell'invio della nuova password")
            else:
                messaggio_stato("errore", "Email non registrata")

    if st.button("← Torna al Login"):
        st.session_state["pagina"] = "Login"
        st.rerun()

def pagina_cambio_password():
    """Pagina per il cambio password obbligatorio."""
    if "utente_reset" not in st.session_state:
        st.session_state["pagina"] = "Login"
        st.rerun()
    
    user = st.session_state["utente_reset"]
    mostra_intestazione("Cambio Password")
    
    with st.form("cambio_password_form"):
        st.markdown(f"**Utente:** {user['nome']} {user['cognome']}")
        nuova_password = st.text_input("Nuova Password", type="password", key="new_pwd")
        conferma_password = st.text_input("Conferma Nuova Password", type="password", key="conf_pwd")
        submit = st.form_submit_button("Cambia Password")
        
        if submit:
            if not nuova_password or not conferma_password:
                messaggio_stato("errore", "Entrambi i campi sono obbligatori")
            elif nuova_password != conferma_password:
                messaggio_stato("errore", "Le password non coincidono")
            else:
                user["password"] = nuova_password
                user["reset_required"] = False
                
                users = carica_utenti()
                for i, u in enumerate(users):
                    if u["email"] == user["email"]:
                        users[i] = user
                        break
                
                if salva_utenti(users):
                    messaggio_stato("successo", "Password cambiata con successo!")
                    st.session_state["utente"] = user
                    st.session_state.pop("utente_reset", None)
                    aggiorna_attivita()
                    st.rerun()
                else:
                    messaggio_stato("errore", "Errore nel salvataggio della nuova password")

def pagina_dashboard():
    """Dashboard principale dell'applicazione."""
    if "utente" not in st.session_state or not st.session_state["utente"]:
        st.session_state["pagina"] = "Login"
        st.rerun()
    
    if not verifica_sessione():
        messaggio_stato("avviso", "Sessione scaduta. Effettua nuovamente il login.")
        st.session_state.clear()
        st.session_state["pagina"] = "Login"
        st.rerun()
    
    aggiorna_attivita()
    utente = st.session_state["utente"]
    
    stile_app()
    mostra_intestazione("Dashboard")
    st.markdown(f"<div class='title-center'>Benvenuto, {utente['nome']}!</div>", unsafe_allow_html=True)
    st.write(f"**Ruolo:** {utente['ruolo']}")
    st.write(f"**Email:** {utente['email']}")
    
    # Caricamento dati
    df_raw, df = load_and_prepare_data()
    if df.empty:
        messaggio_stato("errore", "Impossibile caricare i dati. Contattare l'amministratore.")
        return
    
    # Filtri
    st.markdown("### Filtri")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        rep_sel = st.multiselect(
            "Filtra per Reparto", 
            sorted(df["CodReparto"].unique()), 
            key="filtro_reparto"
        )
        dis_sel = st.multiselect(
            "Filtra per Dislocazione Territoriale", 
            sorted(df["Dislocazione Territoriale"].unique()), 
            key="filtro_dislocazione"
        )
    
    with col2:
        ubi_sel = st.multiselect(
            "Filtra per Ubicazione", 
            sorted(df["Ubicazione"].unique()), 
            key="filtro_ubicazione"
        )
        consumo_vals = sorted(df["Ultimo Consumo"].unique(), key=key_consumo)
        consumo_sel = st.multiselect(
            "Filtra per Ultimo Consumo", 
            consumo_vals, 
            key="filtro_consumo"
        )
    
    with col3:
        min_valore = st.number_input(
            "Valore minimo (€)", 
            min_value=0.0, 
            value=0.0, 
            step=10.0,
            key="filtro_min_valore"
        )
        min_giacenza = st.number_input(
            "Giacenza minima", 
            min_value=0, 
            value=0, 
            step=1,
            key="filtro_min_giacenza"
        )
    
    # Applicazione filtri
    dff = df.copy()
    if rep_sel:
        dff = dff[dff["CodReparto"].isin(rep_sel)]
    if dis_sel:
        dff = dff[dff["Dislocazione Territoriale"].isin(dis_sel)]
    if ubi_sel:
        dff = dff[dff["Ubicazione"].isin(ubi_sel)]
    if consumo_sel:
        dff = dff[dff["Ultimo Consumo"].isin(consumo_sel)]
    
    dff = dff[
        (dff["Valore Complessivo"] >= min_valore) & 
        (dff["Giacenza"] >= min_giacenza)
    ]
    
    # Download dati
    st.download_button(
        "📥 Scarica CSV",
        data=dff.to_csv(index=False, sep=";").encode("utf-8"),
        file_name="sielte_rottamazione.csv",
        mime="text/csv",
        key="download_csv"
    )
    
    # Configurazione griglia
    cols = [
        "_orig_index", "Dislocazione Territoriale", "CodReparto", "Ubicazione",
        "Articolo", "Descrizione", "Giacenza", "Valore Complessivo",
        "Rottamazione", "UserRottamazione", "Data Ultimo Carico",
        "Data Ultimo Consumo", "Ultimo Consumo"
    ]
    
    grid_df = dff[cols].copy()
    grid_df["Valore Complessivo"] = grid_df["Valore Complessivo"].map(
        lambda x: f"€ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )
    
    gb = GridOptionsBuilder.from_dataframe(grid_df)
    gb.configure_column("_orig_index", hide=True)
    gb.configure_column("Rottamazione", 
                       editable=True, 
                       cellEditor="agCheckboxCellEditor",
                       headerCheckboxSelection=True,
                       headerCheckboxSelectionFilteredOnly=True)
    gb.configure_column("UserRottamazione", editable=False)
    
    gb.configure_selection("multiple", use_checkbox=True)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=20)
    gb.configure_grid_options(domLayout="normal")
    
    grid_options = gb.build()
    
    # Visualizzazione griglia
    grid_response = AgGrid(
        grid_df,
        gridOptions=grid_options,
        height=600,
        width="100%",
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        fit_columns_on_grid_load=False,
        theme="streamlit",
        key="main_grid"
    )
    
    # Gestione salvataggio
    updated_data = grid_response["data"]
    
    if "salvataggio_in_corso" not in st.session_state:
        st.session_state["salvataggio_in_corso"] = False
    
    if st.session_state["salvataggio_in_corso"]:
        st.info("⏳ Attendere: salvataggio in corso...")
        background_save(updated_data, df_raw, utente["email"])
        return
    
    if st.button("💾 Salva Modifiche", key="salva_button"):
        st.session_state["salvataggio_in_corso"] = True
        st.experimental_rerun()
    
    # Statistiche
    st.markdown("### Statistiche")
    col_stat1, col_stat2, col_stat3 = st.columns(3)
    
    with col_stat1:
        st.metric("Totale Articoli", len(dff))
    
    with col_stat2:
        st.metric("Da Rottamare", dff["Rottamazione"].sum())
    
    with col_stat3:
        valore_totale = dff["Valore Complessivo"].sum()
        st.metric("Valore Totale", f"€ {valore_totale:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    
    # Logout
    if st.button("🔒 Logout", key="logout_button"):
        st.session_state.clear()
        st.session_state["pagina"] = "Login"
        st.rerun()

# --- Main ---
def main():
    """Funzione principale dell'applicazione."""
    stile_app()
    
    # Inizializzazione session state
    if "pagina" not in st.session_state:
        st.session_state["pagina"] = "Login"
    
    if "utente" not in st.session_state:
        st.session_state["utente"] = None
    
    # Routing delle pagine
    if st.session_state.get("utente_reset"):
        pagina_cambio_password()
    elif st.session_state["pagina"] == "Login":
        pagina_login()
    elif st.session_state["pagina"] == "Registrazione":
        pagina_registrazione()
    elif st.session_state["pagina"] == "Recupera Password":
        pagina_recupera_password()
    elif st.session_state["utente"]:
        pagina_dashboard()
    else:
        st.session_state["pagina"] = "Login"
        st.rerun()

if __name__ == "__main__":
    main()



