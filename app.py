import streamlit as st
import requests
from datetime import datetime
import pandas as pd
from supabase import create_client

# --- KONFIGURACJA ---
SUPABASE_URL = "https://edrlnpuyvpzbdlffwbim.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVkcmxucHV5dnB6YmRsZmZ3YmltIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5NTA4NTksImV4cCI6MjA5MjUyNjg1OX0._dzKIbr9ZmmRfihW7WRmUK_d41RJF7DYAk5aTqjJmZI"
FOOTBALL_TOKEN = "21d27ca30b4246dd92da0c67601362ab"

# Inicjalizacja klienta raz
if "supabase" not in st.session_state:
    st.session_state.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- FUNKCJE ---
def get_fixtures():
    url = "https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED"
    headers = {'X-Auth-Token': FOOTBALL_TOKEN}
    try:
        res = requests.get(url, headers=headers).json()
        matches = res.get('matches', [])
        return [{
            'id': str(m['id']),
            'date': m['utcDate'],
            'home': m['homeTeam']['shortName'] or m['homeTeam']['name'],
            'away': m['awayTeam']['shortName'] or m['awayTeam']['name']
        } for m in matches[:15]]
    except:
        return []

def save_prediction(user_id, match_id, h_score, a_score, scorer):
    try:
        # Bardzo ważne: upewniamy się, że dane są czyste
        data = {
            "user_id": str(user_id),
            "match_id": str(match_id),
            "home_score": int(h_score),
            "away_score": int(a_score),
            "scorer_name": str(scorer)
        }
        # Wykonujemy upsert przez klienta w sesji
        st.session_state.supabase.table("predictions").upsert(data).execute()
        return True
    except Exception as e:
        st.error(f"Błąd zapisu: {e}")
        return False

# --- INTERFEJS ---
st.set_page_config(page_title="Liga Predicty", layout="wide")

# Sprawdzanie czy użytkownik jest w sesji
if 'user_id' not in st.session_state:
    st.title("⚽ Witaj w Liga Predicty")
    st.subheader("Zaloguj się, aby zacząć")
    
    with st.form("login_form"):
        u_email = st.text_input("Email").strip()
        u_pw = st.text_input("Hasło", type="password").strip()
        submit = st.form_submit_button("Zaloguj")
        
        if submit:
            try:
                # Próba logowania
                auth = st.session_state.supabase.auth.sign_in_with_password({"email": u_email, "password": u_pw})
                # Jeśli przeszło, zapisujemy w sesji i odświeżamy
                st.session_state.user_id = auth.user.id
                st.session_state.user_email = auth.user.email
                st.success("Zalogowano! Kliknij jeszcze raz lub odśwież.")
                st.rerun()
            except Exception as e:
                st.error(f"Błąd logowania: {e}")
else:
    # --- PANEL DLA ZALOGOWANEGO ---
    st.title(f"⚽ Powodzenia, {st.session_state.user_email}!")
    
    if st.sidebar.button("Wyloguj"):
        st.session_state.supabase.auth.sign_out()
        del st.session_state.user_id
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["📝 Typuj", "🏆 Ranking", "📋 Moje Typy"])

    with tab1:
        fixtures = get_fixtures()
        if not fixtures:
            st.info("Brak nadchodzących meczów.")
        
        for f in fixtures:
            with st.expander(f"🗓️ {f['date'][:16].replace('T', ' ')} | {f['home']} vs {f['away']}"):
                c1, c2 = st.columns(2)
                h_val = c1.number_input("Gole Dom", 0, 15, key=f"h{f['id']}")
                a_val = c2.number_input("Gole Wyjazd", 0, 15, key=f"a{f['id']}")
                sc = st.text_input("Strzelec", key=f"s{f['id']}")
                
                if st.button("Zapisz", key=f"b{f['id']}"):
                    if not sc:
                        st.warning("Wpisz strzelca!")
                    else:
                        if save_prediction(st.session_state.user_id, f['id'], h_val, a_val, sc):
                            st.toast("Zapisano!") # Małe powiadomienie
                            st.success(f"Typ na {f['home']} - {f['away']} zapisany!")

    with tab2:
        try:
            res = st.session_state.supabase.table("profiles").select("username, points").order("points", desc=True).execute()
            if res.data:
                st.table(pd.DataFrame(res.data))
            else:
                st.write("Brak graczy w rankingu.")
        except:
            st.write("Ranking będzie dostępny wkrótce.")

    with tab3:
        try:
            my = st.session_state.supabase.table("predictions").select("match_id, home_score, away_score, scorer_name").eq("user_id", st.session_state.user_id).execute()
            if my.data:
                st.dataframe(pd.DataFrame(my.data))
            else:
                st.write("Nic jeszcze nie wytypowałeś.")
        except:
            st.write("Nie można pobrać Twoich typów.")
