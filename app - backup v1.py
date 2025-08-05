import streamlit as st
import json
import os
import re

# Percorso file utenti
UTENTI_FILE = "utenti.json"

# Funzione per caricare utenti
def carica_utenti():
    if os.path.exists(UTENTI_FILE):
        try:
            with open(UTENTI_FILE, "r") as f:
                contenuto = f.read().strip()
                if contenuto == "":
                    return []
                return json.loads(contenuto)
        except json.JSONDecodeError:
            st.warning("⚠️ Il file utenti.json è danneggiato. Verrà sovrascritto.")
            return []
    else:
        return []


# Funzione per salvare utenti
def salva_utenti(lista_utenti):
    with open(UTENTI_FILE, "w") as f:
        json.dump(lista_utenti, f, indent=4)

# Stile CSS ispirato al secondo screenshot
def stile_login():
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(135deg, #2c3e50, #3498db);
            color: white;
        }

        /* Etichette e contenuti */
        label, div[data-baseweb="radio"] * {
            color: white !important;
            font-weight: bold;
        }

        /* Radio button della navigazione */
        div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] > p {
            color: white !important;
            font-weight: bold;
        }

        /* Titolo centrato */
        .title-center {
            text-align: center;
            color: white;
            font-size: 2.5em;
            font-weight: bold;
            margin-top: 1em;
            margin-bottom: 0.5em;
        }

        /* Pulsanti */
        .stButton > button {
            background-color: #00bcd4;
            color: white;
            font-weight: bold;
            border-radius: 8px;
            padding: 0.5em 1.5em;
        }

        /* Successo personalizzato */
        .custom-success {
            background-color: #4CAF50;
            padding: 1rem;
            border-radius: 8px;
            color: white;
            font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)

# Login utente
def login():
    st.subheader("Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Accedi"):
        utenti = carica_utenti()
        for utente in utenti:
            if utente["email"] == email and utente["password"] == password:
                st.markdown(f'''
                    <div style="background-color: #4CAF50; padding: 1rem; border-radius: 8px; color: white; font-weight: bold;">
                         Benvenuto {utente['nome']} {utente['cognome']}
                    </div>
                ''',unsafe_allow_html=True)

                return utente
        st.error("Credenziali non valide")
    return None

# Registrazione
def registrazione():
    st.markdown('<div class="title-center">Registrazione</div>', unsafe_allow_html=True)
    nome = st.text_input("Nome")
    cognome = st.text_input("Cognome")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    st.caption("🔐 La password deve contenere almeno 6 caratteri, un numero e un simbolo.")

    ruolo = st.radio("Ruolo", ["User", "Admin"])
    reparti = st.multiselect("Reparti abilitati", ["Magazzino", "Logistica", "Produzione"]) if ruolo == "User" else []

    if st.button("Registra"):
        # ⚠️ Validazioni
        errori = []

        if not nome.strip():
            errori.append("Nome mancante")
        if not cognome.strip():
            errori.append("Cognome mancante")
        if not email.strip():
            errori.append("Email mancante")
        if not password.strip():
            errori.append("Password mancante")

        # Password valida?
        if len(password) < 6 or not re.search(r"\d", password) or not re.search(r"[^\w\s]", password):
            errori.append("Password non conforme ai criteri")

        if ruolo == "User" and not reparti:
            errori.append("Seleziona almeno un reparto")

        if errori:
            for e in errori:
                st.error(f"❌ {e}")
            return

        # Email già registrata?
        utenti = carica_utenti()
        if any(u["email"].lower() == email.lower() for u in utenti):
            st.error("⚠️ Questo indirizzo email è già registrato.")
            return

        nuovo_utente = {
            "nome": nome,
            "cognome": cognome,
            "email": email,
            "password": password,
            "ruolo": ruolo,
            "reparti": reparti if ruolo == "User" else "ALL"
        }

        utenti.append(nuovo_utente)
        salva_utenti(utenti)
        st.markdown('''
            <div style="background-color: #4CAF50; padding: 1rem; border-radius: 8px; color: white; font-weight: bold;">
                ✅ Registrazione completata. Ora puoi fare login.
            </div>
            ''', unsafe_allow_html=True)


# Logo e navigazione
def interfaccia():
    col1, col2 = st.columns([1, 5])
    with col1:
        try:
            st.image("C:\Script\sielte_rottamazione\logo.png", width=90)
        except:
            st.markdown("🧭")
    with col2:
        st.markdown('<div class="title-center">Login</div>', unsafe_allow_html=True)


# MAIN
def main():
    stile_login()
    interfaccia()

    pagina = st.radio("Navigazione", ["Login", "Registrazione"])
    if pagina == "Login":
        utente = login()
        if utente:
            st.write(f"Accesso riuscito come **{utente['ruolo']}**")
    else:
        registrazione()

if __name__ == "__main__":
    main()
