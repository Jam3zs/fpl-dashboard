import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt

st.sidebar.title("FPL Dashboard")

# User input for team names and IDs
st.sidebar.markdown("### Enter your FPL details")
user_team = st.sidebar.text_input("Your Team Name", "Palmer Ham Sandwich")
user_id = st.sidebar.text_input("Your FPL ID", "660915")
rival1_team = st.sidebar.text_input("Rival 1 Team Name", "Slots Flops")
rival1_id = st.sidebar.text_input("Rival 1 FPL ID", "8438056")
rival2_team = st.sidebar.text_input("Rival 2 Team Name", "Klopps and Robbers")
rival2_id = st.sidebar.text_input("Rival 2 FPL ID", "5338703")

# Collect user input into manager_ids dict
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
view = st.sidebar.radio("Select View:", ["Total Points", "Weekly Points", "Points Difference", "Leaderboard Table"])

min_week = int(combined['event'].min())
max_week = int(combined['event'].max())
selected_range = st.sidebar.slider("Select Gameweek Range:", min_value=min_week, max_value=max_week, value=(min_week, max_week))

# Filter by selected gameweek range
filtered = combined[(combined['event'] >= selected_range[0]) & (combined['event'] <= selected_range[1])]

st.title(f"FPL Comparison: {user_team} vs Rivals")

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

st.caption(f"Built for {user_team} 🍞⚽")
