import streamlit as st
import json
import os
import re
import pandas as pd
import smtplib
import random
import time
import string
import threading
from email.message import EmailMessage
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

# --- Funzioni di supporto ---
def calcola_intervallo(dt):
    if pd.isna(dt):
        return "Nessun Consumo"
    delta = pd.Timestamp.today() - dt
    anni  = delta.days // 365
    mesi  = (delta.days % 365) // 30
    if anni > 1:  return f"{anni} Anni"
    if anni == 1: return "1 Anno"
    if mesi > 1:  return f"{mesi} Mesi"
    if mesi == 1: return "1 Mese"
    return "Oggi"

def key_consumo(v):
    if v.startswith("Nessun"): return (2,0)
    parts = v.split()
    num = int(parts[0]) if parts and parts[0].isdigit() else 0
    if "Mese" in v: return (0,num)
    if "Anno" in v: return (1,num)
    return (3,num)

# Configurazione pagina
st.set_page_config(page_title="Sielte Rottamazione", layout="wide")

# Costanti
SMTP_SERVER   = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_EMAIL    = "no.reply.rec.psw@gmail.com"
SMTP_PASSWORD = "usrq vbeu pwap pubp"
UTENTI_FILE   = "utenti.json"
DATA_FILE     = os.path.join("data", "data.xlsx")

# --- Funzioni Utenti ---
def carica_utenti():
    if os.path.exists(UTENTI_FILE):
        try:
            txt = open(UTENTI_FILE, "r").read().strip()
            return json.loads(txt) if txt else []
        except json.JSONDecodeError:
            st.warning("⚠️ Il file utenti.json è danneggiato. Verrà sovrascritto.")
            return []
    return []

def salva_utenti(users):
    with open(UTENTI_FILE, "w") as f:
        json.dump(users, f, indent=4)

# --- Stile CSS ---
def stile_login():
    st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #2c3e50, #3498db); color: white; }
    label, div[data-baseweb="radio"] * { color: white !important; font-weight: bold; }
    .title-center { text-align: center; color: white; font-size: 2.5em; font-weight: bold; margin: 1em 0; }
    .stButton > button { background-color: #00bcd4; color: white; font-weight: bold; border-radius: 8px; }
    .custom-success { background-color: #4CAF50; padding: 1rem; border-radius: 8px; color: white; }
    [data-testid="stDownloadButton"] button { color: black !important; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

def messaggio_successo(testo):
    st.markdown(f"<div class='custom-success'>✅ {testo}</div>", unsafe_allow_html=True)

# --- Password Reset Utilities ---
def genera_password_temporanea(n=10):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(random.choices(chars, k=n))

def invia_email_nuova_password(dest, pwd):
    msg = EmailMessage()
    msg["Subject"] = "Recupero Password - Sielte App"
    msg["From"]    = SMTP_EMAIL
    msg["To"]      = dest
    msg.set_content(f"La tua nuova password temporanea è: {pwd}\nTi verrà chiesto di cambiarla al primo accesso.")
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_EMAIL, SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Errore invio email: {e}")
        return False

# --- Caricamento dati ---
def carica_dataframe():
    df = pd.read_excel(DATA_FILE, engine="openpyxl")
    df.columns = df.columns.str.strip()
    return df

# --- Background save ---
def background_save_logic(updated, df_raw, current_email):
    df2 = df_raw.copy()
    blocked = 0
    for row in updated:
        idx  = int(row["_orig_index"])
        newf = bool(row["Rottamazione"])
        prev = df2.at[idx, "UserRottamazione"]
        if newf and not prev:
            df2.at[idx, "Rottamazione"]     = True
            df2.at[idx, "UserRottamazione"] = current_email
        elif not newf and prev == current_email:
            df2.at[idx, "Rottamazione"]     = False
            df2.at[idx, "UserRottamazione"] = ""
        elif prev and prev != current_email:
            blocked += 1
    df2.to_excel(DATA_FILE, index=False, engine="openpyxl")
    st.session_state.clear()
    st.session_state["salvataggio_bloccati"] = blocked
    st.session_state["pagina"] = "Login"
    st.rerun()

def background_save(updated, df_raw, current_email):
    try:
        background_save_logic(updated, df_raw, current_email)
        st.session_state.clear()
        st.session_state["pagina"] = "Redirect"
        st.rerun()
    except Exception as e:
        st.error(f"Errore durante il salvataggio: {e}")

# --- Login / Registrazione / Reset Password ---
def login():
    st.subheader("Login")
    email = st.text_input("Email")
    pwd   = st.text_input("Password", type="password")
    if st.button("Accedi"):
        for u in carica_utenti():
            if u["email"] == email and u["password"] == pwd:
                if u.get("reset_required"):
                    st.session_state["utente_reset"] = u
                    st.session_state["pagina"]       = "Cambio Password"
                else:
                    messaggio_successo(f"Benvenuto {u['nome']} {u['cognome']}")
                    st.session_state["utente"] = u
                st.rerun()
        st.error("Credenziali non valide")
    if st.button("Recupera Password", type="secondary"):
        st.session_state["pagina"] = "Recupera Password"
        st.rerun()

def cambio_password_forzato():
    u = st.session_state.get("utente_reset")
    st.subheader("Cambio Password")
    temp = st.text_input("Password temporanea", type="password")
    new1 = st.text_input("Nuova password", type="password")
    new2 = st.text_input("Conferma nuova password", type="password")
    if st.button("Cambia password"):
        if temp != u["password"]:
            st.error("Password temporanea non corretta")
        elif new1 != new2:
            st.error("Le nuove password non corrispondono")
        else:
            users = carica_utenti()
            for x in users:
                if x["email"].lower() == u["email"].lower():
                    x["password"]       = new1
                    x["reset_required"] = False
            salva_utenti(users)
            messaggio_successo("Password aggiornata. Effettua login.")
            st.session_state["pagina"] = "Login"
            st.session_state.pop("utente_reset")
            st.rerun()

# --- Dashboard principale ---
def mostra_dashboard(utente):
    stile_login()
    st.markdown(f"<div class='title-center'>Benvenuto, {utente['nome']}!</div>", unsafe_allow_html=True)
    st.write(f"Ruolo: **{utente['ruolo']}**")
    current_email = utente["email"]

    # 1) Carica DataFrame
    try:
        df_raw = carica_dataframe()
    except Exception as e:
        st.error(f"Errore caricamento dati: {e}")
        return

    df_raw["Rottamazione"]     = df_raw.get("Rottamazione", False).fillna(False).astype(bool)
    df_raw["UserRottamazione"] = df_raw.get("UserRottamazione", "").fillna("").astype(str)

    df = df_raw.reset_index().rename(columns={"index": "_orig_index"})
    for c in ["Dislocazione Territoriale","CodReparto","Ubicazione","Articolo","Descrizione"]:
        df[c] = df[c].fillna("TRANSITO").astype(str).str.replace(r"\.0$", "", regex=True)
    df["Giacenza"] = pd.to_numeric(df.get("Giacenza",0), errors="coerce").fillna(0).astype(int)
    df["Valore Complessivo"] = pd.to_numeric(df.get("Valore Complessivo",0), errors="coerce").fillna(0.0)

    df["Data Ultimo Carico"] = pd.to_datetime(df_raw["Data Ultimo Carico"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("-")
    df["Data Ultimo Consumo"] = pd.to_datetime(df_raw["Data Ultimo Consumo"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("-")
    df["Ultimo Consumo"] = pd.to_datetime(df_raw["Data Ultimo Consumo"], errors="coerce").apply(calcola_intervallo)

    st.markdown("### Filtri")
    rep_sel = st.multiselect("Filtra per Reparto", df["CodReparto"].unique(), default=[])
    dis_sel = st.multiselect("Filtra per Dislocazione Territoriale", df["Dislocazione Territoriale"].unique(), default=[])
    ubi_sel = st.multiselect("Filtra per Ubicazione", df["Ubicazione"].unique(), default=[])
    vals    = sorted(df["Ultimo Consumo"].dropna().unique(), key=key_consumo)
    consumo_sel = st.multiselect("Filtra per Ultimo Consumo", vals, default=[])

    dff = df.copy()
    if rep_sel:      dff = dff[dff["CodReparto"].isin(rep_sel)]
    if dis_sel:      dff = dff[dff["Dislocazione Territoriale"].isin(dis_sel)]
    if ubi_sel:      dff = dff[dff["Ubicazione"].isin(ubi_sel)]
    if consumo_sel:  dff = dff[dff["Ultimo Consumo"].isin(consumo_sel)]

    st.download_button("📥 Scarica CSV", data=dff.to_csv(index=False).encode("utf-8"), file_name="tabella_filtrata.csv", mime="text/csv")

    cols = ["_orig_index","Dislocazione Territoriale","CodReparto","Ubicazione","Articolo","Descrizione","Giacenza","Valore Complessivo","Rottamazione","UserRottamazione","Data Ultimo Carico","Data Ultimo Consumo","Ultimo Consumo"]
    grid_df = dff[cols].copy()
    grid_df["Valore Complessivo"] = grid_df["Valore Complessivo"].map(lambda x: f"€ {x:,.2f}".replace(",","X").replace(".",",").replace("X","."))

    gb = GridOptionsBuilder.from_dataframe(grid_df)
    gb.configure_column("_orig_index", hide=True)
    gb.configure_column("Rottamazione", editable=True, cellEditor="agCheckboxCellEditor")
    gb.configure_column("UserRottamazione", editable=False)
    opts = gb.build()

    resp = AgGrid(grid_df, gridOptions=opts, fit_columns_on_grid_load=True, update_mode=GridUpdateMode.VALUE_CHANGED, data_return_mode=DataReturnMode.FILTERED_AND_SORTED)
    updated = resp["data"].to_dict("records") if isinstance(resp["data"], pd.DataFrame) else resp["data"]

    if st.button("Salva"):
        background_save(updated, df_raw, current_email)

    st.markdown(f"**Totale articoli filtrati:** {len(dff)}")
    st.markdown(f"**Articoli da rottamare:** {dff['Rottamazione'].sum()}")

# --- Logo e navigazione ---
def interfaccia():
    c1, c2 = st.columns([1,5])
    with c1:
        try:
            st.image("https://www.confindustriaemilia.it/flex/AppData/Redational/ElencoAssociati/0.11906600%201536649262/e037179fa82dad8532a1077ee51a4613.png", width=180)
        except:
            st.markdown("🧭")
    with c2:
        st.markdown('<div class="title-center">Login</div>', unsafe_allow_html=True)
        
def pagina_transizione():
    stile_login()
    st.markdown("<div class='title-center'>✅ Salvataggio effettuato</div>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>Eseguo il log off e verrai reindirizzato alla pagina di login...</p>", unsafe_allow_html=True)
    st.markdown("""
        <meta http-equiv="refresh" content="3;url=/" />
    """, unsafe_allow_html=True)

# --- Main ---
def main():
    stile_login()
    if "pagina" not in st.session_state:
        st.session_state["pagina"] = "Login"
    if "utente" not in st.session_state:
        st.session_state["utente"] = None

    # Pagina intermedia di transizione
    if st.session_state["pagina"] == "Redirect":
        pagina_transizione()
        return

    # Cambio password forzato
    if st.session_state.get("utente_reset"):
        cambio_password_forzato()
        return

    # Dashboard principale
    if st.session_state["utente"]:
        mostra_dashboard(st.session_state["utente"])
        return

    # Login, registrazione, recupero password
    interfaccia()
    pagine = ["Login", "Registrazione", "Recupera Password"]
    scelta = st.radio("Navigazione", pagine, index=pagine.index(st.session_state["pagina"]))
    st.session_state["pagina"] = scelta

    if scelta == "Login":
        login()
    elif scelta == "Registrazione":
        registrazione()
    else:
        recupera_password()


if __name__ == "__main__":
    main()







