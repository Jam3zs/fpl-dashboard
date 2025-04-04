import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import base64
import seaborn as sns
import io

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

league_options = {}
if user_id:
    try:
        league_options = get_user_leagues(user_id)
        selected_league = st.sidebar.selectbox("Choose Mini-League", list(league_options.keys()))
    except:
        st.sidebar.warning("Unable to load leagues. Check your FPL ID.")
        selected_league = None
else:
    selected_league = None

def fetch_league_rivals(league_id, user_id):
    standings_url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    standings_response = requests.get(standings_url).json()
    rivals = standings_response['standings']['results']

    # Find the index of the user
    user_index = next((i for i, r in enumerate(rivals) if str(r['entry']) == user_id), None)

    if user_index is None:
        return []

    # Try to get the two above
    if user_index >= 2:
        selected = rivals[user_index - 2:user_index]
    else:
        # If at top, take two below instead
        selected = rivals[user_index + 1:user_index + 3]

    return [(r['entry_name'], r['entry']) for r in selected], r['entry']) for r in closest]

try:
    if selected_league:
        league_id = league_options[selected_league]
        rivals = fetch_league_rivals(league_id, user_id)
        rival1_team, rival1_id = rivals[0]
        rival2_team, rival2_id = rivals[1]
    else:
        raise ValueError("No league selected")
except:
    st.sidebar.warning("Could not auto-detect rivals. Check your FPL ID or league data.")
    rival1_team = st.sidebar.text_input("Rival 1 Team Name", "Slots Flops")
    rival1_id = st.sidebar.text_input("Rival 1 FPL ID", "8438056")
    rival2_team = st.sidebar.text_input("Rival 2 Team Name", "Klopps and Robbers")
    rival2_id = st.sidebar.text_input("Rival 2 FPL ID", "5338703")

# Collect manager info
manager_ids = {
    user_team: int(user_id),
    rival1_team: int(rival1_id),
    rival2_team: int(rival2_id)
}

def fetch_history(manager_id):
    url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/history/"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()['current']
    return pd.DataFrame(data)[['event', 'points', 'total_points']]

# Load data
dataframes = {}
for name, mid in manager_ids.items():
    df = fetch_history(mid)
    df = df.rename(columns={
        'points': f'{name} Weekly',
        'total_points': f'{name} Total'
    })
    dataframes[name] = df

# Merge all into a single dataframe
combined = dataframes[list(manager_ids.keys())[0]][['event']].copy()
for name, df in dataframes.items():
    combined = combined.merge(df, on='event', how='outer')

# Sidebar options
view = st.sidebar.radio("Select View:", ["Total Points", "Weekly Points", "Points Difference", "Leaderboard Table", "Weekly Averages", "Biggest Swing"])

min_week = int(combined['event'].min())
max_week = int(combined['event'].max())
selected_range = st.sidebar.slider("Select Gameweek Range:", min_value=min_week, max_value=max_week, value=(min_week, max_week))

# Filter by selected gameweek range
filtered = combined[(combined['event'] >= selected_range[0]) & (combined['event'] <= selected_range[1])]

st.title(f"FPL Comparison: {user_team} vs Rivals")

# Add option to download plot
def get_image_download_link(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    href = f'<a href="data:image/png;base64,{b64}" download="fpl_graph.png">📥 Download this graph as PNG</a>'
    return href

if view in ["Total Points", "Weekly Points"]:
    fig, ax = plt.subplots(figsize=(12, 6))
    for name in manager_ids:
        col = f'{name} Total' if view == "Total Points" else f'{name} Weekly'
        ax.plot(filtered['event'], filtered[col], marker='o', label=name)
    ax.set_ylabel("Total Points" if view == "Total Points" else "Weekly Points")
    ax.set_xlabel("Gameweek")
    ax.set_xticks(filtered['event'])
    ax.legend()
    ax.grid(True)
    st.pyplot(fig)
    st.subheader(f"{view} by Gameweek")
    st.markdown(get_image_download_link(fig), unsafe_allow_html=True)

elif view == "Points Difference":
    base = user_team
    fig, ax = plt.subplots(figsize=(12, 6))
    for name in manager_ids:
        if name != base:
            diff = filtered[f'{base} Total'] - filtered[f'{name} Total']
            ax.plot(filtered['event'], diff, marker='o', label=f"{base} - {name}")
    ax.set_ylabel("Points Ahead")
    ax.set_xlabel("Gameweek")
    ax.set_xticks(filtered['event'])
    ax.legend()
    ax.grid(True)
    st.pyplot(fig)
    st.subheader(f"Points Difference vs {base}")
    st.markdown(get_image_download_link(fig), unsafe_allow_html=True)

elif view == "Leaderboard Table":
    latest = combined[combined['event'] == combined['event'].max()].copy()
    leaderboard = {
        'Manager': [],
        'Total Points': []
    }
    for name in manager_ids:
        leaderboard['Manager'].append(name)
        leaderboard['Total Points'].append(latest[f'{name} Total'].values[0])

    df_leaderboard = pd.DataFrame(leaderboard).sort_values(by="Total Points", ascending=False).reset_index(drop=True)
    st.subheader("Current Leaderboard")
    st.table(df_leaderboard)

elif view == "Weekly Averages":
    averages = {
        'Manager': [],
        'Average Points': []
    }
    for name in manager_ids:
        avg = filtered[f'{name} Weekly'].mean()
        averages['Manager'].append(name)
        averages['Average Points'].append(round(avg, 2))
    df_avg = pd.DataFrame(averages).sort_values(by="Average Points", ascending=False).reset_index(drop=True)
    st.subheader("Average Weekly Points")
    st.table(df_avg)

elif view == "Biggest Swing":
    swings = {
        'Manager': [],
        'Gameweek': [],
        'Swing': []
    }
    for name in manager_ids:
        diffs = filtered[f'{name} Weekly'].diff().abs()
        max_idx = diffs.idxmax()
        swings['Manager'].append(name)
        swings['Gameweek'].append(filtered.loc[max_idx, 'event'])
        swings['Swing'].append(int(diffs[max_idx]))
    df_swing = pd.DataFrame(swings).sort_values(by="Swing", ascending=False).reset_index(drop=True)
    st.subheader("Biggest Gameweek Point Swings")
    st.table(df_swing)

# Shareable link instructions
share_url = f"https://fpl-dashboard-palmer.streamlit.app/?user_team={user_team}&user_id={user_id}&rival1_team={rival1_team}&rival1_id={rival1_id}&rival2_team={rival2_team}&rival2_id={rival2_id}"
st.markdown("---")
st.markdown("### 🔗 Share This Setup")
st.code(share_url)
st.caption(f"Built for {user_team} 🍞⚽")
