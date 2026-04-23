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

# TUTAJ WPISZ SWÓJ MAIL (ten sam, na który założyłeś konto gracza)
ADMIN_EMAIL = "k1rj4nek@gmail.com" 

if "supabase" not in st.session_state:
    st.session_state.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 2. FUNKCJE POBIERANIA I ZAPISU
# ==========================================

@st.cache_data(ttl=600)
def get_fixtures():
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
    except: return []

def save_prediction(user_id, match_id, h_score, a_score, scorer):
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
        st.error(f"Błąd zapisu: {e}"); return False

# ==========================================
# 3. LOGIKA ROZLICZANIA (5 PKT / 2 PKT)
# ==========================================

def update_ranking():
    st.info("Trwa pobieranie wyników i przeliczanie punktów...")
    url = "https://api.football-data.org/v4/competitions/PL/matches?status=FINISHED"
    headers = {'X-Auth-Token': FOOTBALL_TOKEN}
    
    try:
        res = requests.get(url, headers=headers).json()
        finished_matches = res.get('matches', [])
        
        preds_res = st.session_state.supabase.table("predictions").select("*").execute()
        all_preds = preds_res.data
        
        user_points = {} 

        for match in finished_matches:
            m_id = str(match['id'])
            real_h = match['score']['fullTime']['home']
            real_a = match['score']['fullTime']['away']
            
            # Wyciąganie strzelców w kolejności czasowej
            match_goals = match.get('goals', [])
            all_scorers = []
            for g in match_goals:
                if g.get('player'):
                    all_scorers.append(g['player']['name'].lower())

            # Kto strzelił pierwszy w meczu?
            first_scorer_name = all_scorers[0] if all_scorers else None

            # Sprawdzamy typy graczy dla tego meczu
            match_preds = [p for p in all_preds if p['match_id'] == m_id]
            
            for p in match_preds:
                pts = 0
                u_id = p['user_id']
                ph, pa = p['home_score'], p['away_score']
                p_scorer = p['scorer_name'].lower().strip()

                # --- PUNKTY ZA WYNIK ---
                if ph == real_h and pa == real_a:
                    pts += 3 # Trafiony wynik
                elif (ph > pa and real_h > real_a) or (ph < pa and real_h < real_a) or (ph == pa and real_h == real_a):
                    pts += 1 # Trafiona tendencja

                # --- PUNKTY ZA STRZELCA ---
                if first_scorer_name and p_scorer in first_scorer_name:
                    pts += 5 # Trafiony PIERWSZY strzelec
                elif any(p_scorer in s for s in all_scorers):
                    pts += 2 # Trafiony strzelec (ale nie pierwszy)

                user_points[u_id] = user_points.get(u_id, 0) + pts

        # Aktualizacja punktów w Supabase
        for u_id, total in user_points.items():
            st.session_state.supabase.table("profiles").update({"points": total}).eq("id", u_id).execute()
        
        st.success("Ranking zaktualizowany!")
        st.rerun()
    except Exception as e:
        st.error(f"Błąd rozliczania: {e}")

# ==========================================
# 4. INTERFEJS UŻYTKOWNIKA
# ==========================================

st.set_page_config(page_title="Liga Predicty 25/26", page_icon="⚽", layout="wide")

if 'user_id' not in st.session_state:
    st.title("⚽ Witaj w Liga Predicty")
    with st.container():
        email_input = st.text_input("Email").strip()
        pw_input = st.text_input("Hasło", type="password").strip()
        if st.button("Zaloguj do gry"):
            try:
                auth = st.session_state.supabase.auth.sign_in_with_password({"email": email_input, "password": pw_input})
                if auth.user:
                    st.session_state.user_id = auth.user.id
                    st.session_state.user_email = auth.user.email
                    st.rerun()
            except: st.error("Błąd logowania.")
else:
    # --- BOCZNY PANEL ---
    st.sidebar.success(f"Zalogowany jako: {st.session_state.user_email}")
    
    # Przycisk Admina widoczny tylko dla Ciebie
    if st.session_state.user_email == ADMIN_EMAIL:
        st.sidebar.divider()
        st.sidebar.subheader("👑 Panel Administratora")
        if st.sidebar.button("🔄 Przelicz wszystkie punkty"):
            update_ranking()

    if st.sidebar.button("Wyloguj"):
        st.session_state.supabase.auth.sign_out()
        del st.session_state['user_id']
        st.rerun()

    # --- ZAKŁADKI ---
    tab1, tab2, tab3 = st.tabs(["📝 Typuj", "🏆 Ranking", "📋 Moje Typy"])

    with tab1:
        st.header("Mecze do wytypowania")
        fixtures = get_fixtures()
        now = datetime.now()
        for f in fixtures:
            is_blocked = now > f['raw_date']
            with st.expander(f"🗓️ {f['display_date']} | {f['home']} vs {f['away']}"):
                if is_blocked:
                    st.error("🔒 Mecz już się rozpoczął.")
                else:
                    c1, c2 = st.columns(2)
                    h_val = c1.number_input(f"Gole {f['home']}", 0, 15, key=f"h{f['id']}")
                    a_val = c2.number_input(f"Gole {f['away']}", 0, 15, key=f"a{f['id']}")
                    sc = st.text_input("Nazwisko strzelca", key=f"s{f['id']}")
                    if st.button("Zatwierdź Predict", key=f"b{f['id']}"):
                        if not sc: st.warning("Wpisz strzelca!")
                        elif save_prediction(st.session_state.user_id, f['id'], h_val, a_val, sc):
                            st.success("Zapisano typ!")

    with tab2:
        st.subheader("Tabela Ligi")
        res = st.session_state.supabase.table("profiles").select("username, points").order("points", desc=True).execute()
        if res.data:
            st.table(pd.DataFrame(res.data))

    with tab3:
        st.subheader("Twoje wysłane typy")
        my = st.session_state.supabase.table("predictions").select("*").eq("user_id", st.session_state.user_id).execute()
        if my.data:
            st.dataframe(pd.DataFrame(my.data))
