import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
from supabase import create_client

# ==========================================
# 1. KONFIGURACJA
# ==========================================
SUPABASE_URL = "https://edrlnpuyvpzbdlffwbim.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVkcmxucHV5dnB6YmRsZmZ3YmltIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5NTA4NTksImV4cCI6MjA5MjUyNjg1OX0._dzKIbr9ZmmRfihW7WRmUK_d41RJF7DYAk5aTqjJmZI"
FOOTBALL_TOKEN = "21d27ca30b4246dd92da0c67601362ab"

# Inicjalizacja klienta w sesji - to naprawia błąd podwójnego logowania
if "supabase" not in st.session_state:
    st.session_state.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 2. FUNKCJE
# ==========================================

@st.cache_data(ttl=600)
def get_fixtures():
    """Pobiera mecze i przelicza czas na polski (UTC+2)."""
    url = "https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED"
    headers = {'X-Auth-Token': FOOTBALL_TOKEN}
    try:
        res = requests.get(url, headers=headers).json()
        matches = res.get('matches', [])
        formatted = []
        for m in matches:
            utc_date = datetime.strptime(m['utcDate'], "%Y-%m-%dT%H:%M:%SZ")
            pl_date = utc_date + timedelta(hours=2)
            formatted.append({
                'id': str(m['id']),
                'display_date': pl_date.strftime("%d.%m.%Y %H:%M"),
                'raw_date': pl_date,
                'home': m['homeTeam']['shortName'] or m['homeTeam']['name'],
                'away': m['awayTeam']['shortName'] or m['awayTeam']['name']
            })
        return formatted[:15]
    except:
        return []

def save_prediction(user_id, match_id, h_score, a_score, scorer):
    """Zapisuje typ do bazy."""
    try:
        data = {
            "user_id": str(user_id),
            "match_id": str(match_id),
            "home_score": int(h_score),
            "away_score": int(a_score),
            "scorer_name": str(scorer).strip()
        }
        st.session_state.supabase.table("predictions").upsert(data).execute()
        return True
    except Exception as e:
        st.error(f"Błąd zapisu: {e}")
        return False

# ==========================================
# 3. INTERFEJS
# ==========================================

st.set_page_config(page_title="Liga Predicty 25/26", page_icon="⚽", layout="wide")

# Logika logowania
if 'user_id' not in st.session_state:
    st.title("⚽ Witaj w Liga Predicty")
    
    # Używamy kontenera, żeby formularz był stabilny
    with st.container():
        email = st.text_input("Email").strip()
        password = st.text_input("Hasło", type="password").strip()
        
        if st.button("Zaloguj do gry"):
            try:
                # Próba autoryzacji
                auth_res = st.session_state.supabase.auth.sign_in_with_password({
                    "email": email, 
                    "password": password
                })
                
                # Jeśli sukces, zapisujemy dane w sesji
                if auth_res.user:
                    st.session_state.user_id = auth_res.user.id
                    st.session_state.user_email = auth_res.user.email
                    st.success("Zalogowano pomyślnie!")
                    st.rerun() # To przeładowuje stronę już jako zalogowany
            except Exception as e:
                st.error("Błędne dane logowania. Spróbuj ponownie.")

else:
    # PANEL ZALOGOWANEGO UŻYTKOWNIKA
    st.sidebar.success(f"Zalogowany: {st.session_state.user_email}")
    if st.sidebar.button("Wyloguj"):
        st.session_state.supabase.auth.sign_out()
        del st.session_state['user_id']
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["📝 Typuj Mecze", "🏆 Ranking", "📋 Moje Typy"])

    with tab1:
        st.header("Nadchodzące mecze (Czas PL)")
        fixtures = get_fixtures()
        now = datetime.now()
        
        if not fixtures:
            st.info("Brak nadchodzących meczów do typowania.")
            
        for f in fixtures:
            is_blocked = now > f['raw_date']
            
            with st.expander(f"🗓️ {f['display_date']} | {f['home']} vs {f['away']}"):
                if is_blocked:
                    st.error("🔒 Mecz już się rozpoczął. Typowanie zablokowane.")
                else:
                    c1, c2 = st.columns(2)
                    h_val = c1.number_input(f"Gole {f['home']}", 0, 15, key=f"h{f['id']}")
                    a_val = c2.number_input(f"Gole {f['away']}", 0, 15, key=f"a{f['id']}")
                    
                    sc = st.text_input("Kto strzeli gola? (Nazwisko)", key=f"s{f['id']}")
                    
                    if st.button("Zatwierdź Predict", key=f"b{f['id']}"):
                        if not sc:
                            st.warning("Musisz podać strzelca!")
                        else:
                            if save_prediction(st.session_state.user_id, f['id'], h_val, a_val, sc):
                                st.success(f"Zapisano typ na mecz {f['home']}!")

    with tab2:
        st.subheader("Ranking")
        try:
            res = st.session_state.supabase.table("profiles").select("username, points").order("points", desc=True).execute()
            if res.data:
                df_ranking = pd.DataFrame(res.data)
                df_ranking.columns = ["Gracz", "Punkty"]
                st.table(df_ranking)
            else:
                st.write("Ranking będzie dostępny wkrótce.")
        except:
            st.write("Błąd ładowania rankingu.")

    with tab3:
        st.subheader("Twoje ostatnie wysłane typy")
        try:
            my_preds = st.session_state.supabase.table("predictions").select("match_id, home_score, away_score, scorer_name").eq("user_id", st.session_state.user_id).execute()
            if my_preds.data:
                st.dataframe(pd.DataFrame(my_preds.data))
            else:
                st.write("Nie masz jeszcze zapisanych typów.")
        except:
            st.write("Błąd pobierania Twoich typów.")
