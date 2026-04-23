import streamlit as st
import requests
from datetime import datetime
import pandas as pd
from supabase import create_client

# --- KONFIGURACJA ---
SUPABASE_URL = "https://edrlnpuyvpzbdlffwbim.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVkcmxucHV5dnB6YmRsZmZ3YmltIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5NTA4NTksImV4cCI6MjA5MjUyNjg1OX0._dzKIbr9ZmmRfihW7WRmUK_d41RJF7DYAk5aTqjJmZI"
FOOTBALL_TOKEN = "21d27ca30b4246dd92da0c67601362ab"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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
        data = {
            "user_id": user_id,
            "match_id": str(match_id),
            "home_score": int(h_score),
            "away_score": int(a_score),
            "scorer_name": scorer
        }
        # Używamy rpc lub bezpośredniego upsert
        supabase.table("predictions").upsert(data).execute()
        return True
    except Exception as e:
        st.error(f"Błąd zapisu: {e}")
        return False

# --- INTERFEJS ---
st.set_page_config(page_title="Liga Predicty", layout="wide")
st.title("⚽ Liga Predicty 25/26")

if 'user_id' not in st.session_state:
    st.info("Zaloguj się, aby zacząć grę.")
    with st.form("login"):
        email = st.text_input("Email")
        pw = st.text_input("Hasło", type="password")
        if st.form_submit_button("Zaloguj"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": pw})
                st.session_state.user_id = res.user.id
                st.session_state.user_email = res.user.email
                st.rerun()
            except Exception as e:
                st.error("Nieprawidłowy email lub hasło.")
else:
    st.sidebar.success(f"Gracz: {st.session_state.user_email}")
    if st.sidebar.button("Wyloguj"):
        del st.session_state.user_id
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["📝 Typuj", "🏆 Ranking", "📋 Moje Typy"])

    with tab1:
        fixtures = get_fixtures()
        if not fixtures:
            st.warning("Nie znaleziono nadchodzących meczów.")
        for f in fixtures:
            with st.expander(f"🗓️ {f['date'][:16].replace('T', ' ')} | {f['home']} vs {f['away']}"):
                c1, c2 = st.columns(2)
                h_s = c1.number_input(f"Gole {f['home']}", 0, 15, key=f"h{f['id']}")
                a_s = c2.number_input(f"Gole {f['away']}", 0, 15, key=f"a{f['id']}")
                scorer = st.text_input("Strzelec (Nazwisko)", key=f"s{f['id']}")
                
                if st.button("Zapisz Typ", key=f"b{f['id']}"):
                    if not scorer:
                        st.warning("Podaj strzelca!")
                    elif save_prediction(st.session_state.user_id, f['id'], h_s, a_s, scorer):
                        st.success("Zapisano pomyślnie!")

    with tab2:
        st.subheader("Ranking")
        try:
            res = supabase.table("profiles").select("username, points").order("points", desc=True).execute()
            if res.data:
                st.table(pd.DataFrame(res.data))
            else:
                st.info("Brak graczy w rankingu.")
        except:
            st.error("Nie udało się pobrać rankingu (Tabela profiles może być pusta).")

    with tab3:
        st.subheader("Twoje wysłane typy")
        try:
            my = supabase.table("predictions").select("match_id, home_score, away_score, scorer_name").eq("user_id", st.session_state.user_id).execute()
            if my.data and len(my.data) > 0:
                st.dataframe(pd.DataFrame(my.data))
            else:
                st.info("Jeszcze nic nie wytypowałeś.")
        except:
            st.error("Nie udało się pobrać Twoich typów.")
