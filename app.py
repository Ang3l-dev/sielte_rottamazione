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
from tempfile import NamedTemporaryFile
from shutil import move
from datetime import datetime
from threading import Lock
import pandas as _pd  # per gli helper di dedup

# =========================
# Configurazione pagina
# =========================
st.set_page_config(page_title="Sielte Rottamazione", layout="wide")

# =========================
# Costanti e variabili globali
# =========================
SMTP_SERVER   = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_EMAIL    = "no.reply.rec.psw@gmail.com"
SMTP_PASSWORD = "usrq vbeu pwap pubp"   # usa una app password reale (Google App Password)
UTENTI_FILE   = "utenti.json"

DATA_DIR      = "data"
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE     = os.path.join(DATA_DIR, "data.xlsx")

_write_lock = Lock()  # per salvataggi concorrenti

# =========================
# Utility utenti
# =========================
def carica_utenti():
    if os.path.exists(UTENTI_FILE):
        try:
            with open(UTENTI_FILE, "r", encoding="utf-8") as f:
                txt = f.read().strip()
            return json.loads(txt) if txt else []
        except json.JSONDecodeError:
            st.warning("⚠️ Il file utenti.json è danneggiato. Verrà sovrascritto.")
            return []
    return []

def salva_utenti(users):
    with open(UTENTI_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

# =========================
# Helper: header duplicati (solo rinomina, nessuna riga toccata)
# =========================
def _find_duplicate_columns(cols):
    s = _pd.Series([str(c) for c in cols])
    dupe_mask = s.duplicated(keep=False)
    if not dupe_mask.any():
        return []
    names = s[dupe_mask].tolist()
    pos = [(i, str(c)) for i, c in enumerate(cols) if c in names]
    return pos  # list of (index, name)

def _make_unique_columns_inplace(df, label="(df)"):
    cols = _pd.Series([str(c).strip() for c in df.columns], dtype="object")
    if cols.duplicated(keep=False).any():
        counts = cols.groupby(cols).cumcount()
        new_cols = cols.where(counts.eq(0), cols + "__" + (counts + 1).astype(str))
        df.columns = new_cols
        return True
    return False

def _assert_or_fix_unique(df, label, on_error="fix"):
    dupes = _find_duplicate_columns(df.columns)
    if not dupes:
        return
    if on_error == "fix":
        _make_unique_columns_inplace(df, label=label)
    elif on_error == "raise":
        msg = " | ".join([f"[{i}] {name}" for i, name in dupes])
        st.error(f"❌ Colonne duplicate in **{label}**: {msg}")
        st.stop()
    else:
        # warn: non blocchiamo, ma non rinominiamo
        msg = " | ".join([f"[{i}] {name}" for i, name in dupes])
        st.warning(f"⚠️ Colonne duplicate in **{label}**: {msg}")

# =========================
# Stile
# =========================
def stile_login():
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(135deg, #002244 0%, #003366 50%, #0077C8 100%) !important;
            color: white;
        }
        label, div[data-baseweb="radio"] *, .st-emotion-cache-10trblm, .stMarkdown p {
            color: white !important;
        }
        .title-center {
            text-align: center;
            color: white;
            font-size: 2rem;
            font-weight: 700;
            margin: 1rem 0 0.5rem 0;
        }
        .stButton > button {
            background-color: #00bcd4 !important;
            color: white !important;
            font-weight: 700 !important;
            border-radius: 10px !important;
            padding: 0.5rem 1.25rem !important;
            border: none !important;
        }
        .custom-success {
            background-color: #2e7d32;
            padding: 0.75rem 1rem;
            border-radius: 8px;
            color: #fff;
            font-weight: 700;
        }
        [data-testid="stDownloadButton"] button {
            color: black !important;
            font-weight: bold !important;
        }
        </style>
    """, unsafe_allow_html=True)

def messaggio_successo(text):
    st.markdown(f"<div class='custom-success'>✅ {text}</div>", unsafe_allow_html=True)

# =========================
# Email / password
# =========================
def genera_password_temporanea(n=10):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(random.choices(chars, k=n))

def invia_email_nuova_password(dest, pwd):
    msg = EmailMessage()
    msg["Subject"] = "Recupero Password - Sielte App"
    msg["From"]    = SMTP_EMAIL
    msg["To"]      = dest
    msg.set_content(
        f"La tua nuova password temporanea è: {pwd}\n"
        f"Ti verrà chiesto di cambiarla al primo accesso."
    )
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_EMAIL, SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Errore invio email: {e}")
        return False

# =========================
# Cache data
# =========================
@st.cache_data(show_spinner=False)
def load_data(path):
    df_raw = pd.read_excel(path, engine="openpyxl")
    return df_raw

def save_excel_safe(df: pd.DataFrame, path: str):
    """Salvataggio sicuro: scrive su un temporaneo e poi sostituisce il file originale."""
    with _write_lock:
        with NamedTemporaryFile("wb", delete=False, suffix=".xlsx") as tmp:
            temp_name = tmp.name
        df.to_excel(temp_name, index=False)
        move(temp_name, path)

# =========================
# Prep DF per dashboard (crea RowID)
# =========================
def prepara_df(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = df_raw.copy()

    # Colonne attese
    required_cols = [
        "Dislocazione Territoriale","CodReparto","Ubicazione",
        "Articolo","Descrizione","Giacenza","Valore Complessivo",
        "Rottamazione","UserRottamazione",
        "Data Ultimo Carico","Data Ultimo Consumo"
    ]
    for c in required_cols:
        if c not in df.columns:
            if c == "Rottamazione":
                df[c] = False
            elif c == "UserRottamazione":
                df[c] = ""
            else:
                df[c] = None

    # Normalizza stringhe e TRANSITO
    for c in ["Dislocazione Territoriale","CodReparto","Ubicazione","Articolo","Descrizione"]:
        df[c] = (
            df[c].astype(object)
                 .where(pd.notna(df[c]), "TRANSITO")
                 .astype(str)
                 .str.replace(r"\.0$", "", regex=True)
                 .str.strip()
        )

    # Numeri
    df["Giacenza"] = pd.to_numeric(df["Giacenza"], errors="coerce").fillna(0).astype(int)
    df["Valore Complessivo"] = pd.to_numeric(df["Valore Complessivo"], errors="coerce").fillna(0.0)

    # Date + formattazione
    df["_dt_ultimo_carico"]  = pd.to_datetime(df["Data Ultimo Carico"],  errors="coerce")
    df["_dt_ultimo_consumo"] = pd.to_datetime(df["Data Ultimo Consumo"], errors="coerce")
    df["Data Ultimo Carico"]  = df["_dt_ultimo_carico"].dt.strftime("%d/%m/%Y").fillna("-")
    df["Data Ultimo Consumo"] = df["_dt_ultimo_consumo"].dt.strftime("%d/%m/%Y").fillna("-")

    # Ultimo consumo (testo + chiave)
    def calcola_intervallo(dt):
        if pd.isna(dt):
            return "Nessun Consumo"
        delta = pd.Timestamp.today().normalize() - dt.normalize()
        giorni = max(delta.days, 0)
        anni = giorni // 365
        mesi = (giorni % 365) // 30
        if anni > 1:  return f"{anni} Anni"
        if anni == 1: return "1 Anno"
        if mesi > 1:  return f"{mesi} Mesi"
        if mesi == 1: return "1 Mese"
        return "Oggi"

    df["Ultimo Consumo"] = df["_dt_ultimo_consumo"].apply(calcola_intervallo)

    def key_consumo(v):
        if v.startswith("Nessun"): return (2, 0)
        parts = v.split()
        num = int(parts[0]) if parts and parts[0].isdigit() else 0
        if "Mese" in v: return (0, num)
        if "Anno" in v: return (1, num)
        return (3, num)

    df["_key_consumo"] = df["Ultimo Consumo"].map(key_consumo)

    # Booleani / stringhe (dtype robusti)
    df["Rottamazione"] = pd.Series(df["Rottamazione"], dtype="boolean").fillna(False).astype(bool)
    df["UserRottamazione"] = pd.Series(df["UserRottamazione"], dtype="string").fillna("").astype(str)

    # Se qualcuno avesse salvato "RowID" nel file, rimuovilo PRIMA di crearla ex-novo
    if "RowID" in df.columns:
        df = df.drop(columns=["RowID"])

    # Chiave stabile di riga = indice originale
    df = df.reset_index().rename(columns={"index": "RowID"})
    df["RowID"] = df["RowID"].astype(int)

    return df

# =========================
# Autenticazione
# =========================
def login():
    st.subheader("Login")
    email = st.text_input("Email")
    pwd   = st.text_input("Password", type="password")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Accedi"):
            for u in carica_utenti():
                if u["email"].lower() == email.lower() and u["password"] == pwd:
                    if u.get("reset_required"):
                        st.session_state["utente_reset"] = u
                        st.session_state["pagina"] = "Cambio Password"
                    else:
                        messaggio_successo(f"Benvenuto {u['nome']} {u['cognome']}")
                        st.session_state["utente"] = u
                    st.rerun()
            st.error("Credenziali non valide")
    with col2:
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
        elif len(new1) < 6 or not re.search(r"\d", new1) or not re.search(r"[^\w\s]", new1):
            st.error("La nuova password non rispetta i requisiti")
        else:
            users = carica_utenti()
            for x in users:
                if x["email"].lower() == u["email"].lower():
                    x["password"] = new1
                    x["reset_required"] = False
            salva_utenti(users)
            messaggio_successo("Password aggiornata. Effettua login.")
            st.session_state["pagina"] = "Login"
            st.session_state.pop("utente_reset", None)
            st.rerun()

def carica_reparti_da_excel():
    try:
        df0 = load_data(DATA_FILE)
        df0.columns = df0.columns.str.strip()
        return sorted(df0["CodReparto"].dropna().astype(str).unique())
    except Exception:
        return []

def registrazione():
    st.markdown('<div class="title-center">Registrazione</div>', unsafe_allow_html=True)
    nome    = st.text_input("Nome")
    cognome = st.text_input("Cognome")
    email   = st.text_input("Email")
    pwd     = st.text_input("Password", type="password")
    pwd2    = st.text_input("Conferma Password", type="password")
    st.caption("🔐 Min 6 caratteri, almeno un numero e un simbolo.")
    reps = carica_reparti_da_excel()
    sel  = st.multiselect("Reparti abilitati", reps)
    if st.button("Registra"):
        errs = []
        if not nome.strip():    errs.append("Nome mancante")
        if not cognome.strip(): errs.append("Cognome mancante")
        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_regex, email): errs.append("Formato email non valido")
        if pwd != pwd2:         errs.append("Le password non corrispondono")
        if len(pwd) < 6 or not re.search(r"\d", pwd) or not re.search(r"[^\w\s]", pwd):
            errs.append("Password non conforme")
        if not sel:             errs.append("Seleziona almeno un reparto")
        users = carica_utenti()
        if any(u["email"].lower()==email.lower() for u in users):
            errs.append("⚠️ Email già registrata")
        if errs:
            for e in errs: st.error(f"❌ {e}")
            return
        nuovo = {
            "nome": nome, "cognome": cognome, "email": email,
            "password": pwd, "ruolo": "User",
            "reparti": sel,  "reset_required": False
        }
        users.append(nuovo)
        salva_utenti(users)
        st.success("✅ Registrazione avvenuta. Effettua il login.")
        st.session_state["pagina"] = "Login"
        st.rerun()

def recupera_password():
    st.markdown('<div class="title-center">Recupera Password</div>', unsafe_allow_html=True)
    email = st.text_input("Inserisci email per reset")
    if st.button("Invia nuova password"):
        users = carica_utenti()
        u = next((x for x in users if x["email"].lower()==email.lower()), None)
        if not u:
            st.error("⚠️ Email non trovata")
            return
        new_pwd = genera_password_temporanea()
        u["password"]       = new_pwd
        u["reset_required"] = True
        salva_utenti(users)
        if invia_email_nuova_password(email, new_pwd):
            st.success("✅ Mail inviata. Controlla la posta.")
        else:
            st.error("❌ Errore invio email")

# =========================
# SALVATAGGIO modifiche
# =========================
def background_save_logic(updated_rows, df_view, df_raw, current_email):
    """
    updated_rows: records dopo l'editing della griglia (contengono RowID)
    df_view: dataframe "prepara_df" usato per AgGrid (con RowID)
    df_raw:  dataframe originale letto da disco (senza RowID)
    """
    # normalizza updated_rows
    upd_df = pd.DataFrame(updated_rows) if isinstance(updated_rows, list) else updated_rows.copy()

    if "RowID" not in upd_df.columns:
        st.error("Impossibile salvare: chiave 'RowID' mancante nei dati della griglia.")
        return
    if "Rottamazione" not in upd_df.columns:
        st.info("Nessuna colonna 'Rottamazione' nei dati aggiornati. Nulla da salvare.")
        return

    # prendiamo solo ciò che serve
    upd_df = upd_df[["RowID", "Rottamazione"]].copy()

    # mappa RowID -> nuovo flag
    new_flags = dict(zip(upd_df["RowID"].astype(int), upd_df["Rottamazione"].astype(bool)))

    # garantisci colonne/tipi su df_raw
    if "Rottamazione" not in df_raw.columns:
        df_raw["Rottamazione"] = False
    if "UserRottamazione" not in df_raw.columns:
        df_raw["UserRottamazione"] = ""
    df_raw["Rottamazione"] = pd.Series(df_raw["Rottamazione"], dtype="boolean").fillna(False)
    df_raw["UserRottamazione"] = pd.Series(df_raw["UserRottamazione"], dtype="string").fillna("")

    # applica solo se cambia
    changed = 0
    for _, row_view in df_view.iterrows():
        rowid = int(row_view["RowID"])
        if rowid in new_flags:
            old_flag = bool(row_view["Rottamazione"])
            new_flag = bool(new_flags[rowid])
            if old_flag != new_flag:
                df_raw.loc[rowid, "Rottamazione"] = new_flag
                df_raw.loc[rowid, "UserRottamazione"] = (current_email if new_flag else "")
                changed += 1

    if changed > 0:
        try:
            save_excel_safe(df_raw, DATA_FILE)
            load_data.clear()
            st.success(f"✅ Salvato! ({changed} modifiche)")
            st.rerun()
        except Exception as e:
            st.error(f"Errore durante il salvataggio: {e}")
    else:
        st.info("Nessuna modifica da salvare.")

# =========================
# Dashboard
# =========================
def mostra_dashboard(utente):
    stile_login()
    st.markdown(f"<div class='title-center'>Benvenuto, {utente['nome']}!</div>", unsafe_allow_html=True)
    current_email = utente["email"]

    # 1) leggi da cache
    try:
        df_raw = load_data(DATA_FILE)
    except Exception as e:
        st.error(f"Errore caricamento Excel: {e}")
        return

    # 2) prepara per visualizzazione
    _assert_or_fix_unique(df_raw, "df_raw (dopo load_data)", on_error="fix")
    df_view = prepara_df(df_raw)
    _assert_or_fix_unique(df_view, "df_view (dopo prepara_df)", on_error="fix")

    # 3) Filtri
    st.markdown("### Filtri")
    c1, c2, c3 = st.columns(3)
    with c1:
        rep_sel = st.multiselect("Reparto", sorted(df_view["CodReparto"].unique()), default=[])
    with c2:
        dis_sel = st.multiselect("Dislocazione Territoriale", sorted(df_view["Dislocazione Territoriale"].unique()), default=[])
    with c3:
        ubi_sel = st.multiselect("Ubicazione", sorted(df_view["Ubicazione"].unique()), default=[])

    # chiave ordinamento sicura per "Ultimo Consumo"
    key_map = dict(zip(df_view["Ultimo Consumo"], df_view["_key_consumo"]))
    vals = sorted(df_view["Ultimo Consumo"].dropna().unique(), key=lambda x: key_map.get(x, (9, 0)))
    consumo_sel = st.multiselect("Ultimo Consumo", vals, default=[])

    dff = df_view.copy()
    if rep_sel:      dff = dff[dff["CodReparto"].isin(rep_sel)]
    if dis_sel:      dff = dff[dff["Dislocazione Territoriale"].isin(dis_sel)]
    if ubi_sel:      dff = dff[dff["Ubicazione"].isin(ubi_sel)]
    if consumo_sel:  dff = dff[dff["Ultimo Consumo"].isin(consumo_sel)]
    _assert_or_fix_unique(dff, "dff (dopo filtri)", on_error="fix")

    # 4) Download CSV (drop colonne tecniche)
    export_df = dff.drop(columns=["_key_consumo","_dt_ultimo_carico","_dt_ultimo_consumo"], errors="ignore").copy()
    _assert_or_fix_unique(export_df, "export_df (prima del CSV)", on_error="fix")
    st.download_button(
        "📥 Scarica CSV",
        data=export_df.to_csv(index=False).encode("utf-8"),
        file_name=f"tabella_filtrata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

    # 5) Griglia (paginazione 20 righe + scroll)
    cols_show = [
        "RowID",  # chiave visibile, stretta
        "Dislocazione Territoriale","CodReparto","Ubicazione",
        "Articolo","Descrizione","Giacenza","Valore Complessivo",
        "Rottamazione","UserRottamazione","Data Ultimo Carico",
        "Data Ultimo Consumo","Ultimo Consumo"
    ]
    cols_show_exist = [c for c in cols_show if c in dff.columns]
    grid_df = dff[cols_show_exist].copy()
    _assert_or_fix_unique(grid_df, "grid_df (prima di AgGrid)", on_error="fix")

    # dtypes coerenti per la checkbox
    if "Rottamazione" in grid_df.columns:
        grid_df["Rottamazione"] = pd.Series(grid_df["Rottamazione"], dtype="boolean").fillna(False).astype(bool)

    # formattazione valore (se presente)
    if "Valore Complessivo" in grid_df.columns:
        grid_df["Valore Complessivo"] = grid_df["Valore Complessivo"].map(
            lambda x: f"€ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X",".")
        )

    gb = GridOptionsBuilder.from_dataframe(grid_df)

    # RowID visibile, non editabile, pinnato
    if "RowID" in grid_df.columns:
        gb.configure_column(
            "RowID",
            headerName="ID",
            editable=False,
            width=70,
            maxWidth=80,
            pinned=True
        )

    if "Rottamazione" in grid_df.columns:
        gb.configure_column("Rottamazione", editable=True, cellEditor="agCheckboxCellEditor")
    if "UserRottamazione" in grid_df.columns:
        gb.configure_column("UserRottamazione", editable=False)

    # paginazione 20 righe
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=20)

    grid_opts = gb.build()

    resp = AgGrid(
        grid_df,
        gridOptions=grid_opts,
        height=520,  # scrollbar verticale (rotella/barra)
        fit_columns_on_grid_load=True,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        enable_enterprise_modules=False
    )

    updated = resp["data"]
    updated_records = updated.to_dict("records") if isinstance(updated, pd.DataFrame) else updated

    # 6) SALVA
    if st.button("Salva"):
        background_save_logic(updated_records, dff, df_raw, current_email)

    # 7) Statistiche
    st.markdown(f"**Totale articoli filtrati:** {len(dff)}")
    st.markdown(f"**Articoli da rottamare (filtro corrente):** {int(dff['Rottamazione'].sum())}")

# =========================
# Header e routing
# =========================
def interfaccia():
    c1, c2 = st.columns([1,5])
    with c1:
        try:
            st.image(
                "https://www.confindustriaemilia.it/flex/AppData/Redational/ElencoAssociati/0.11906600%201536649262/e037179fa82dad8532a1077ee51a4613.png",
                width=180
            )
        except Exception:
            st.markdown("🧭")
    with c2:
        st.markdown('<div class="title-center">Login</div>', unsafe_allow_html=True)

def main():
    stile_login()
    if "pagina" not in st.session_state: st.session_state["pagina"] = "Login"
    if "utente" not in st.session_state: st.session_state["utente"] = None

    # Se manca il file Excel, creane uno vuoto con colonne minime
    if not os.path.exists(DATA_FILE):
        df_init = pd.DataFrame(columns=[
            "Dislocazione Territoriale","CodReparto","Ubicazione",
            "Articolo","Descrizione","Giacenza","Valore Complessivo",
            "Rottamazione","UserRottamazione","Data Ultimo Carico","Data Ultimo Consumo"
        ])
        save_excel_safe(df_init, DATA_FILE)
        load_data.clear()

    # Forza cambio password?
    if st.session_state.get("utente_reset"):
        cambio_password_forzato()
        return

    # Utente già dentro?
    if st.session_state["utente"]:
        mostra_dashboard(st.session_state["utente"])
        return

    # Schermate pubbliche
    interfaccia()
    pagine = ["Login","Registrazione","Recupera Password"]
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
