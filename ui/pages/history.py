import streamlit as st
from datetime import date, timedelta

from src.utils.database import get_workouts_filtered
from ui.shared import format_set, parse_json_list

PAGE_SIZE = 10


@st.cache_data(ttl=60)
def _load_filtered_workouts(start_date: str, end_date: str, title_query: str, min_volume: float, max_volume: float):
	return get_workouts_filtered(
		start_date=start_date,
		end_date=end_date,
		title_query=title_query,
		min_volume=min_volume,
		max_volume=max_volume,
	)


def _extract_muscle_groups(rows: list[dict]) -> list[str]:
	groups = set()
	for row in rows:
		groups.update(parse_json_list(row.get("muscle_groups")))
	return sorted(group for group in groups if group)


def _filter_by_muscle_groups(rows: list[dict], selected_groups: list[str]) -> list[dict]:
	if not selected_groups:
		return rows
	selected = set(selected_groups)
	return [
		row for row in rows
		if selected.intersection(parse_json_list(row.get("muscle_groups")))
	]


def _render_summary(rows: list[dict]):
	total_volume = sum(float(row.get("total_volume_kg") or 0) for row in rows)
	readiness_scores = [float(row["readiness_score"]) for row in rows if row.get("readiness_score") is not None]
	average_readiness = round(sum(readiness_scores) / len(readiness_scores), 1) if readiness_scores else "N/A"

	col1, col2, col3 = st.columns(3)
	with col1:
		with st.container(border=True):
			st.metric("Workouts", len(rows))
	with col2:
		with st.container(border=True):
			st.metric("Volume in View", f"{total_volume:,.0f} kg")
	with col3:
		with st.container(border=True):
			st.metric("Avg Readiness", average_readiness)


def _source_badge(source: str) -> str:
	if source == "fitbit":
		return "🔵 Fitbit"
	return "🟠 Strava"


def _render_workout_card(row: dict):
	title = row.get("workout_title") or "Workout"
	source = row.get("source", "strava")
	badge = _source_badge(source)
	volume_kg = float(row.get("total_volume_kg") or 0)
	calories = row.get("calories")
	workout_type = row.get("workout_type") or ""

	# Build header line
	header_parts = [f"{row.get('date')} — {title}"]
	if volume_kg > 0:
		header_parts.append(f"{volume_kg:,.0f} kg")
	elif calories:
		header_parts.append(f"{float(calories):,.0f} cal")
	header_parts.append(badge)
	header = " · ".join(header_parts)

	with st.expander(header):
		# For Fitbit non-exercise workouts, show duration/calories/HR instead of sets
		if source == "fitbit" and int(row.get("exercise_count") or 0) == 0:
			meta_left, meta_mid, meta_right = st.columns(3)
			with meta_left:
				duration = row.get("duration_min")
				st.metric("Duration", f"{float(duration):.0f} min" if duration is not None else "N/A")
			with meta_mid:
				st.metric("Calories", f"{float(calories):,.0f}" if calories else "N/A")
			with meta_right:
				distance = row.get("distance_km")
				st.metric("Distance", f"{float(distance):.1f} km" if distance else "N/A")

			if workout_type:
				st.caption(f"Type: {workout_type.title()}")

			# Show HR zones if available
			hr_zones_raw = row.get("hr_zones")
			if hr_zones_raw:
				zones = parse_json_list(hr_zones_raw)
				if zones:
					st.caption("Heart Rate Zones")
					for zone in zones:
						name = zone.get("name", "")
						minutes = zone.get("minutes", 0)
						if minutes > 0:
							st.write(f"  {name}: {minutes} min")
		else:
			# Standard Strava/exercise workout card
			meta_left, meta_mid, meta_right = st.columns(3)
			with meta_left:
				st.metric("Exercises", int(row.get("exercise_count") or 0))
			with meta_mid:
				st.metric("Sets", int(row.get("set_count") or 0))
			with meta_right:
				duration = row.get("duration_min")
				st.metric("Duration", f"{float(duration):.0f} min" if duration is not None else "N/A")

			if row.get("readiness_label"):
				st.caption(f"Readiness: {row['readiness_label']}")

			for exercise in parse_json_list(row.get("exercises_raw")):
				muscle_group = exercise.get("muscle_group", "other")
				exercise_name = exercise.get("name", "Exercise")
				with st.container(border=True):
					st.write(f"**{exercise_name}** ({muscle_group})")
					for set_data in exercise.get("sets", []):
						st.write(format_set(set_data))


def _render_pagination(total_rows: int):
	total_pages = max(1, (total_rows + PAGE_SIZE - 1) // PAGE_SIZE)
	current_page = st.session_state.get("history_page", 0)
	st.session_state.history_page = min(current_page, total_pages - 1)

	prev_col, info_col, next_col = st.columns([1, 2, 1])
	with prev_col:
		if st.button("Previous", disabled=st.session_state.history_page == 0, use_container_width=True):
			st.session_state.history_page -= 1
			st.rerun()
	with info_col:
		st.caption(f"Page {st.session_state.history_page + 1} of {total_pages}")
	with next_col:
		if st.button("Next", disabled=st.session_state.history_page >= total_pages - 1, use_container_width=True):
			st.session_state.history_page += 1
			st.rerun()


st.header("Workout History")
st.caption("Browse synced workouts from the local cache.")

default_start = date.today() - timedelta(days=30)
date_values = st.date_input("Date range", value=(default_start, date.today()))
if isinstance(date_values, tuple) and len(date_values) == 2:
	start_value, end_value = date_values
else:
	start_value, end_value = default_start, date.today()

filters_col1, filters_col2, filters_col3 = st.columns([3, 2, 2])
with filters_col1:
	title_query = st.text_input("Search by title")
with filters_col2:
	min_volume = float(st.number_input("Min volume (kg)", min_value=0.0, value=0.0, step=50.0))
with filters_col3:
	max_volume = float(st.number_input("Max volume (kg)", min_value=0.0, value=100000.0, step=100.0))

all_rows = _load_filtered_workouts(start_value.isoformat(), end_value.isoformat(), title_query, min_volume, max_volume)

# Source filter
source_options = sorted(set(r.get("source", "strava") for r in all_rows)) if all_rows else []
if len(source_options) > 1:
	selected_sources = st.multiselect("Source", options=[s.title() for s in source_options], default=[s.title() for s in source_options])
	all_rows = [r for r in all_rows if (r.get("source", "strava")).title() in selected_sources]

available_groups = _extract_muscle_groups(all_rows)
selected_groups = st.multiselect("Muscle groups", options=available_groups)
filtered_rows = _filter_by_muscle_groups(all_rows, selected_groups)

filter_signature = (
	start_value.isoformat(),
	end_value.isoformat(),
	title_query,
	min_volume,
	max_volume,
	tuple(selected_groups),
)

if st.session_state.get("history_filters") != filter_signature:
	st.session_state.history_filters = filter_signature
	st.session_state.history_page = 0

if "history_page" not in st.session_state:
	st.session_state.history_page = 0

if filtered_rows:
	_render_summary(filtered_rows)
	st.divider()

	start_index = st.session_state.history_page * PAGE_SIZE
	end_index = start_index + PAGE_SIZE
	page_rows = filtered_rows[start_index:end_index]

	for row in page_rows:
		_render_workout_card(row)

	_render_pagination(len(filtered_rows))
else:
	st.info("No workouts match the selected filters.")