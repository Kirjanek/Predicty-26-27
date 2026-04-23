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
ADMIN_EMAIL = "k1rj4nek@gmail.com"

if "supabase" not in st.session_state:
    st.session_state.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 2. LOGIKA BIZNESOWA
# ==========================================
def login_user(email, password):
    try:
        auth = st.session_state.supabase.auth.sign_in_with_password({"email": email, "password": password})
        if auth.user:
            st.session_state.user_id = auth.user.id
            st.session_state.user_email = auth.user.email
            return True
    except: return False
    return False

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
        data = {"user_id": user_id, "match_id": match_id, "home_score": h_score, "away_score": a_score, "scorer_name": scorer}
        st.session_state.supabase.table("predictions").upsert(data).execute()
        return True
    except Exception as e:
        st.error(f"Błąd bazy: {e}")
        return False

def update_ranking():
    # Pobieramy zakończone mecze i przeliczamy punkty (logika 5 pkt / 2 pkt)
    st.info("Przeliczanie punktów...")
    url = "https://api.football-data.org/v4/competitions/PL/matches?status=FINISHED"
    headers = {'X-Auth-Token': FOOTBALL_TOKEN}
    try:
        res = requests.get(url, headers=headers).json()
        finished = res.get('matches', [])
        preds = st.session_state.supabase.table("predictions").select("*").execute().data
        user_points = {}

        for m in finished:
            m_id = str(m['id'])
            real_h, real_a = m['score']['fullTime']['home'], m['score']['fullTime']['away']
            goals = [g['player']['name'].lower() for g in m.get('goals', []) if g.get('player')]
            first_scorer = goals[0] if goals else None

            for p in [x for x in preds if x['match_id'] == m_id]:
                pts = 0
                ph, pa, ps = p['home_score'], p['away_score'], p['scorer_name'].lower().strip()
                # Wynik
                if ph == real_h and pa == real_a: pts += 3
                elif (ph > pa and real_h > real_a) or (ph < pa and real_h < real_a) or (ph == pa and real_h == real_a): pts += 1
                # Strzelec
                if first_scorer and ps in first_scorer: pts += 5
                elif any(ps in s for s in goals): pts += 2
                user_points[p['user_id']] = user_points.get(p['user_id'], 0) + pts

        for u_id, total in user_points.items():
            st.session_state.supabase.table("profiles").update({"points": total}).eq("id", u_id).execute()
        st.success("Ranking zaktualizowany!")
    except Exception as e: st.error(f"Błąd: {e}")

# ==========================================
# 3. INTERFEJS
# ==========================================
st.set_page_config(page_title="Liga Predicty", page_icon="⚽")

if 'user_id' not in st.session_state:
    st.title("⚽ Liga Predicty 25/26")
    with st.form("login"):
        u = st.text_input("Email")
        p = st.text_input("Hasło", type="password")
        if st.form_submit_button("Zaloguj"):
            if login_user(u, p): st.rerun()
            else: st.error("Błędne dane.")
else:
    st.sidebar.title(f"Witaj, {st.session_state.user_email.split('@')[0]}!")
    if st.session_state.user_email == ADMIN_EMAIL:
        if st.sidebar.button("🔄 Przelicz Ranking"): update_ranking()
    if st.sidebar.button("Wyloguj"):
        st.session_state.supabase.auth.sign_out()
        del st.session_state['user_id']
        st.rerun()

    t1, t2, t3 = st.tabs(["📝 Typuj", "🏆 Ranking", "📋 Moje Typy"])

    with t1:
        for f in get_fixtures():
            with st.expander(f"🗓️ {f['display_date']} | {f['home']} - {f['away']}"):
                c1, c2 = st.columns(2)
                h = c1.number_input(f"Gole {f['home']}", 0, 15, key=f"h{f['id']}")
                a = c2.number_input(f"Gole {f['away']}", 0, 15, key=f"a{f['id']}")
                s = st.text_input("Strzelec (Nazwisko)", key=f"s{f['id']}")
                if st.button("Zapisz", key=f"b{f['id']}"):
                    if s and save_prediction(st.session_state.user_id, f['id'], h, a, s):
                        st.success("Zapisano!")

    with t2:
        df_rank = pd.DataFrame(st.session_state.supabase.table("profiles").select("username, points").order("points", desc=True).execute().data)
        if not df_rank.empty: st.table(df_rank)
        else: st.write("Ranking jest jeszcze pusty.")

    with t3:
        data = st.session_state.supabase.table("predictions").select("match_id, home_score, away_score, scorer_name, created_at").eq("user_id", st.session_state.user_id).execute().data
        if data:
            df = pd.DataFrame(data)
            df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%d.%m %H:%M')
            st.dataframe(df, use_container_width=True)
