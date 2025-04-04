import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import base64
import seaborn as sns
import io
import numpy as np
import seaborn as sns

st.set_page_config(page_title="FPL Dashboard", layout="wide", initial_sidebar_state="expanded")

# Apply Streamlit dark theme colors
sns.set_theme(style="darkgrid")

st.sidebar.title("FPL Dashboard")

# User input for team name and ID
st.sidebar.markdown("### Enter your FPL details")
user_team = st.sidebar.text_input("Your Team Name", "Palmer Ham Sandwich")
user_id = st.sidebar.text_input("Your FPL ID", "660915")

# Fetch leagues for user
@st.cache_data(show_spinner=False)
def get_user_leagues(user_id):
    url = f"https://fantasy.premierleague.com/api/entry/{user_id}/"
    data = requests.get(url).json()
    leagues = data['leagues']['classic']
    return {league['name']: league['id'] for league in leagues}

@st.cache_data(show_spinner=False)
def fetch_league_standings(league_id):
    standings = []
    page = 1
    found_user = False
    while True:
        url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/?page_standings={page}"
        data = requests.get(url).json()
        results = data['standings']['results']
        if not results:
            break
        standings.extend(results)
        # Check if user's ID is in this page
        if any(str(r['entry']) == str(user_id) for r in results):
            found_user = True
        if data['standings']['has_next']:
            page += 1
        else:
            break
    if not found_user:
        st.sidebar.warning("Your team wasn't found in this mini-league. You may not be ranked yet or the league is too large.")
    return standings

league_options = {}
standings = []
if user_id:
    try:
        league_options = get_user_leagues(user_id)
        selected_league = st.sidebar.selectbox("Choose Mini-League", list(league_options.keys()))
        if selected_league:
            league_id = league_options[selected_league]
            standings = fetch_league_standings(league_id)
    except:
        st.sidebar.warning("Unable to load leagues or standings. Check your FPL ID.")
        selected_league = None
else:
    selected_league = None

# Auto-pick closest rivals
def find_closest_above(user_id, standings):
    user_index = next((i for i, r in enumerate(standings) if str(r['entry']) == user_id), None)
    if user_index is None:
        return [], [], None
    user_rank = standings[user_index]['rank']
    rivals_above = [r for r in standings[max(0, user_index - 2):user_index] if str(r['entry']) != user_id]
    start = max(0, user_index - 25)
    end = min(len(standings), user_index + 26)
    nearby = [r for i, r in enumerate(standings[start:end]) if str(r['entry']) != user_id]
    return rivals_above[:2], nearby, user_rank

try:
    if standings:
        auto_rivals, nearby_rivals, user_rank = find_closest_above(user_id, standings)
        rival1_team, rival1_id = auto_rivals[0]['entry_name'], auto_rivals[0]['entry']
        rival2_team, rival2_id = auto_rivals[1]['entry_name'], auto_rivals[1]['entry']
    else:
        raise ValueError("No standings available")
except:
    user_rank = None
    st.sidebar.warning("Could not auto-detect rivals. Check your FPL ID or league data.")
    rival1_team = st.sidebar.text_input("Rival 1 Team Name", "Slots Flops")
    rival1_id = st.sidebar.text_input("Rival 1 FPL ID", "8438056")
    rival2_team = st.sidebar.text_input("Rival 2 Team Name", "Klopps and Robbers")
    rival2_id = st.sidebar.text_input("Rival 2 FPL ID", "5338703")

extra_rivals = st.sidebar.multiselect("Select additional rivals from top 50:", [f"{r['entry_name']} (ID: {r['entry']})" for r in nearby_rivals], [])

# Collect manager info
manager_ids = {
    user_team: {'id': int(user_id), 'rank': user_rank}
}
manager_ids[rival1_team] = {'id': int(rival1_id), 'rank': next((r['rank'] for r in standings if r['entry'] == int(rival1_id)), None)}
manager_ids[rival2_team] = {'id': int(rival2_id), 'rank': next((r['rank'] for r in standings if r['entry'] == int(rival2_id)), None)}

for item in extra_rivals:
    name_id = item.split(" (ID: ")
    name = name_id[0]
    rid = int(name_id[1].replace(")", ""))
    rival_rank = next((r['rank'] for r in standings if r['entry'] == rid), None)
    manager_ids[name] = {'id': rid, 'rank': rival_rank}

def fetch_history(manager_id):
    url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/history/"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()['current']
    return pd.DataFrame(data)[['event', 'points', 'total_points']]

# Load data
raw_scores = {}
dataframes = {}
for name, info in manager_ids.items():
    mid = info['id']
    df = fetch_history(mid)
    df = df.rename(columns={
        'points': f'{name} Weekly',
        'total_points': f'{name} Total'
    })
    dataframes[name] = df
    raw_scores[name] = df['points'].tolist()

# Merge all into a single dataframe
combined = dataframes[list(manager_ids.keys())[0]][['event']].copy()
for name, df in dataframes.items():
    combined = combined.merge(df, on='event', how='outer')

# Sidebar options
view = st.sidebar.radio("Select View:", ["Total Points", "Weekly Points", "Points Difference", "Leaderboard Table", "Weekly Averages", "Biggest Swing", "Best/Worst Gameweeks", "Rolling Averages", "Form Indicator", "Head-to-Head Heatmap"])

min_week = int(combined['event'].min())
max_week = int(combined['event'].max())
selected_range = st.sidebar.slider("Select Gameweek Range:", min_value=min_week, max_value=max_week, value=(min_week, max_week))

filtered = combined[(combined['event'] >= selected_range[0]) & (combined['event'] <= selected_range[1])]

if user_rank:
    st.markdown(f"### 🏅 Your current rank in '{selected_league}': **{user_rank}**")

st.title(f"FPL Comparison: {user_team} vs Rivals")

# Add option to download plot
def get_image_download_link(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    href = f'<a href="data:image/png;base64,{b64}" download="fpl_graph.png">📥 Download this graph as PNG</a>'
    return href

if view == "Best/Worst Gameweeks":
    stats = []
    for name in manager_ids:
        points = combined[f"{name} Weekly"]
        best_gw = points.idxmax()
        worst_gw = points.idxmin()
        stats.append({
            'Manager': name,
            'Best GW': combined.loc[best_gw, 'event'],
            'Best Points': int(points.max()),
            'Worst GW': combined.loc[worst_gw, 'event'],
            'Worst Points': int(points.min())
        })
    st.subheader("🔥 Best & 💣 Worst Gameweeks")
    st.table(pd.DataFrame(stats))

elif view == "Rolling Averages":
    fig, ax = plt.subplots(figsize=(12, 6))
    for name in manager_ids:
        combined[f'{name} MA3'] = combined[f'{name} Weekly'].rolling(window=3).mean()
        ax.plot(filtered['event'], combined[f'{name} MA3'], marker='o', label=name)
    ax.set_title("📊 3-Week Rolling Averages")
    ax.set_xlabel("Gameweek")
    ax.set_ylabel("Rolling Average Points")
    ax.legend()
    st.pyplot(fig)

elif view == "Form Indicator":
    form = []
    for name in manager_ids:
        scores = combined[f'{name} Weekly']
        delta = scores.diff(periods=3)
        indicator = "🔺 Up" if delta.iloc[-1] > 0 else "🔻 Down"
        form.append({"Manager": name, "Form Trend (last 3 GW)": indicator})
    st.subheader("📈 Form Indicator (last 3 GWs)")
    st.table(pd.DataFrame(form))

elif view == "Head-to-Head Heatmap":
    all_weeks = combined['event']
    names = list(manager_ids.keys())
    h2h = pd.DataFrame(index=names, columns=names, data=0)
    for gw in all_weeks:
        scores = {name: combined.loc[combined['event'] == gw, f'{name} Weekly'].values[0] for name in names}
        for a in names:
            for b in names:
                if a != b:
                    h2h.at[a, b] += 1 if scores[a] > scores[b] else 0
    st.subheader("⚔️ Head-to-Head Wins")
    sns.heatmap(h2h.astype(int), annot=True, fmt="d", cmap="RdYlGn")
    st.pyplot()

# (Retain previous views like Total Points, Weekly Points, etc. here...)

# Shareable link instructions
share_url = f"https://fpl-dashboard-palmer.streamlit.app/?user_team={user_team}&user_id={user_id}"
st.markdown("---")
st.markdown("### 🔗 Share This Setup")
st.code(share_url)
st.caption(f"Built for {user_team} 🍞⚽")
