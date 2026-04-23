import streamlit as st
import requests
from datetime import datetime
import pandas as pd
from supabase import create_client

# ==========================================
# 1. KONFIGURACJA
# ==========================================
SUPABASE_URL = "https://edrlnpuyvpzbdlffwbim.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVkcmxucHV5dnB6YmRsZmZ3YmltIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5NTA4NTksImV4cCI6MjA5MjUyNjg1OX0._dzKIbr9ZmmRfihW7WRmUK_d41RJF7DYAk5aTqjJmZI"
FOOTBALL_DATA_TOKEN = "21d27ca30b4246dd92da0c67601362ab"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 2. FUNKCJE
# ==========================================

def get_fixtures():
    """Pobiera mecze Premier League z Football-Data.org."""
    url = "https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED"
    headers = {'X-Auth-Token': FOOTBALL_DATA_TOKEN}
    try:
        res = requests.get(url, headers=headers).json()
        matches = res.get('matches', [])
        formatted = []
        for m in matches:
            formatted.append({
                'fixture_id': str(m['id']),
                'date': m['utcDate'],
                'home_team': m['homeTeam']['shortName'] or m['homeTeam']['name'],
                'away_team': m['awayTeam']['shortName'] or m['awayTeam']['name']
            })
        return formatted[:15]
    except:
        return []

def save_prediction(user_id, match_id, h_score, a_score, scorer):
    """Zapisuje typ do bazy Supabase."""
    data = {
        "user_id": user_id,
        "match_id": match_id,
        "home_score": int(h_score),
        "away_score": int(a_score),
        "scorer_name": scorer,
        "created_at": datetime.now().isoformat()
    }
    try:
        # Używamy upsert, żeby gracz mógł zmieniać typ do czasu meczu
        supabase.table("predictions").upsert(data).execute()
        return True
    except Exception as e:
        st.error(f"Błąd bazy: {e}")
        return False

# ==========================================
# 3. INTERFEJS STREAMLIT
# ==========================================

st.set_page_config(page_title="Predicty 25/26", page_icon="⚽", layout="wide")
st.title("⚽ Liga Predicty - Sezon 2025/2026")

# --- LOGOWANIE ---
if 'user_id' not in st.session_state:
    st.subheader("Zaloguj się, aby typować")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Hasło", type="password")
        if st.form_submit_button("Wejdź do gry"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state['user_id'] = res.user.id
                st.session_state['user_email'] = res.user.email
                st.rerun()
            except:
                st.error("Nieprawidłowy email lub hasło.")
else:
    # --- PANEL BOCZNY ---
    st.sidebar.success(f"Zalogowany: {st.session_state['user_email']}")
    if st.sidebar.button("Wyloguj się"):
        del st.session_state['user_id']
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["📝 Typuj Mecze", "🏆 Ranking", "📋 Moje Typy"])

    # --- TAB 1: TYPOWANIE ---
    with tab1:
        st.header("Nadchodzące mecze Premier League")
        fixtures = get_fixtures()
        
        if not fixtures:
            st.warning("Nie udało się pobrać meczów. Sprawdź Token API.")
        
        for m in fixtures:
            # Formatowanie daty dla użytkownika
            clean_date = m['date'].replace('T', ' ').replace('Z', '')
            
            with st.expander(f"🗓️ {clean_date[:16]} | {m['home_team']} vs {m['away_team']}"):
                col1, col2 = st.columns(2)
                h_score = col1.number_input(f"Gole {m['home_team']}", 0, 15, key=f"h_{m['fixture_id']}")
                a_score = col2.number_input(f"Gole {m['away_team']}", 0, 15, key=f"a_{m['fixture_id']}")
                
                scorer = st.text_input("Kto strzeli gola? (Nazwisko)", key=f"s_{m['fixture_id']}")
                
                if st.button("Wyślij Predict", key=f"btn_{m['fixture_id']}"):
                    if not scorer:
                        st.error("Wpisz nazwisko strzelca!")
                    else:
                        if save_prediction(st.session_state['user_id'], m['fixture_id'], h_score, a_score, scorer):
                            st.success("Zapisano!")

    # --- TAB 2: RANKING ---
    with tab2:
        st.header("Ranking")
        try:
            res = supabase.table("profiles").select("username, points").order("points", desc=True).execute()
            if res.data:
                st.table(pd.DataFrame(res.data))
            else:
                st.info("Ranking jest pusty.")
        except:
            st.error("Błąd ładowania rankingu.")

    # --- TAB 3: MOJE TYPY ---
    with tab3:
        st.header("Twoje ostatnie typy")
        try:
            my_preds = supabase.table("predictions").select("match_id, home_score, away_score, scorer_name").eq("user_id", st.session_state['user_id']).execute()
            if my_preds.data:
                st.dataframe(pd.DataFrame(my_preds.data))
            else:
                st.write("Jeszcze nic nie wytypowałeś.")
        except:
            st.error("Błąd bazy danych.")
