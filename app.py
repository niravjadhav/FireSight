import sys
from pathlib import Path
import json

import streamlit as st
import numpy as np
import pandas as pd
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go

# Add parent directory to sys.path to allow importing from src
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.main import FireSightOrchestrator
from src.config import PUNE_CONFIG

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="FireSight AI — Emergency Intelligence Platform",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# CUSTOM CSS FOR EXECUTIVE/COMMAND CENTER THEME
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* Main container tweaks */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    
    /* Header Container */
    .header-box {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        border-left: 6px solid #ef4444;
        color: #ffffff;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .header-title {
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0;
        color: #f8fafc;
    }
    .header-subtitle {
        font-size: 0.95rem;
        color: #94a3b8;
        margin-top: 0.25rem;
    }

    /* Metric Card Styling */
    .metric-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        color: #f8fafc;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .metric-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
        font-weight: 600;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        margin: 0.2rem 0;
    }
    .metric-badge {
        display: inline-block;
        padding: 0.2em 0.6em;
        font-size: 0.75rem;
        font-weight: 600;
        border-radius: 4px;
    }
    .badge-danger { background-color: #7f1d1d; color: #fca5a5; }
    .badge-warning { background-color: #78350f; color: #fde68a; }
    .badge-success { background-color: #064e3b; color: #6ee7b7; }
    .badge-info { background-color: #0c4a6e; color: #7dd3fc; }

    /* Custom Alert Boxes */
    .stAlert {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Orchestrator
@st.cache_resource
def load_orchestrator():
    return FireSightOrchestrator()

orchestrator = load_orchestrator()

# -----------------------------------------------------------------------------
# SIDEBAR CONTROLS
# -----------------------------------------------------------------------------
st.sidebar.image("https://img.icons8.com/isometric/100/fire-element.png", width=60)
st.sidebar.title("FireSight AI")
st.sidebar.caption("Wildfire Monitoring & Analytics")
st.sidebar.divider()

st.sidebar.subheader("🕹️ Execution Mode")
mode = st.sidebar.radio(
    "Target Scope",
    ["Pune Region Auto-Monitor", "Manual Coordinate Target"],
    index=0
)

if mode == "Manual Coordinate Target":
    lat = st.sidebar.number_input("Target Latitude", value=PUNE_CONFIG["lat"], format="%.4f")
    lon = st.sidebar.number_input("Target Longitude", value=PUNE_CONFIG["lon"], format="%.4f")
else:
    lat = PUNE_CONFIG["lat"]
    lon = PUNE_CONFIG["lon"]
    st.sidebar.success(f"📍 Auto-Target: Pune ({lat}, {lon})")

st.sidebar.divider()
run_pipeline = st.sidebar.button("🚀 Run Intelligence Pipeline", use_container_width=True, type="primary")
test_copernicus = st.sidebar.button("🔐 Test Copernicus Connection", use_container_width=True)

# Test credentials and catalogue access without requiring a current FIRMS fire.
if test_copernicus:
    with st.spinner("Testing Copernicus OAuth and Sentinel-2 catalogue access..."):
        try:
            check = orchestrator.test_copernicus_connection(lat, lon)
            st.sidebar.success("Copernicus authentication successful.")
            st.sidebar.info(check["message"])
            st.sidebar.write(f"Sentinel-2 scenes found in the last 90 days: {check['scene_count']}")
            if check.get("diagnostics"):
                st.sidebar.caption(
                    f"Catalogue returned {check['diagnostics'].get('raw_feature_count', 0)} "
                    f"features across {check['diagnostics'].get('pages_read', 0)} page(s)."
                )
            if check.get("best_scene"):
                st.sidebar.caption(
                    f"Clearest scene: {check['best_scene']['date']} · "
                    f"cloud cover: {check['best_scene']['cloud_cover']}%"
                )
        except Exception as exc:
            st.sidebar.error(f"Copernicus connection failed: {exc}")

# -----------------------------------------------------------------------------
# MAIN HEADER
# -----------------------------------------------------------------------------
st.markdown("""
<div class="header-box">
    <div class="header-title"> FireSight AI — Command Center</div>
    <div class="header-subtitle">Real-time Earth observation, environmental risk calculation & damage assessment pipeline.</div>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# PIPELINE EXECUTION & DISPLAY
# -----------------------------------------------------------------------------
if run_pipeline or 'pipeline_res' in st.session_state:
    if run_pipeline:
        with st.spinner("⚡ Fetching satellite streams, weather models, and running risk neural net..."):
            is_auto = (mode == "Pune Region Auto-Monitor")
            st.session_state['pipeline_res'] = orchestrator.run_pipeline(lat, lon, is_pune_auto=is_auto)

    res = st.session_state['pipeline_res']

    # --- TOP EXECUTIVE METRICS ROW: restore the original point-oriented cards ---
    risk = res.get("wildfire_risk", {}) or {}
    fwi_result = risk.get("fwi", {}) or {}
    fwi_components = fwi_result.get("components", {}) or {}
    active_records = res.get("active_fire", {}).get("all_nearby", []) or []
    historical = res.get("historical_match", {}) or {}
    damage = res.get("damage_assessment", {}) or {}
    severity = res.get("severity", {}) or {}

    c1, c2, c3, c4 = st.columns(4)

    # Card 1: FWI calculated for the exact selected coordinate.
    point_fwi = fwi_components.get("FWI", risk.get("score"))
    if point_fwi is not None:
        fwi_display = f"{float(point_fwi):.2f}"
        fwi_level = str(risk.get("level", "UNAVAILABLE")).upper()
        fwi_detail = "Selected coordinate"
    else:
        fwi_display = "N/A"
        fwi_level = "UNAVAILABLE"
        fwi_detail = "Insufficient weather-history data"
    fwi_badge = "badge-danger" if fwi_level in ("HIGH", "VERY HIGH", "EXTREME") else (
        "badge-warning" if fwi_level == "MODERATE" else "badge-success"
    )
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Fire Weather Index (FWI)</div>
            <div class="metric-value">{fwi_display}</div>
            <span class="metric-badge {fwi_badge}">{fwi_level}</span>
            <div style="font-size:0.75rem;color:#cbd5e1;margin-top:0.45rem;">{fwi_detail}</div>
        </div>
        """, unsafe_allow_html=True)

    # Card 2: retain the existing FIRMS search and its 100 km detection radius.
    detection_count = len(active_records)
    if detection_count:
        latest_detection = max(
            (str(item.get("acq_date", "")) for item in active_records),
            default="date unavailable"
        )
        activity_text = f"{detection_count:,} detections · latest {latest_detection}"
        activity_label = "DETECTED"
        activity_badge = "badge-danger"
    else:
        activity_text = "No detections returned by FIRMS"
        activity_label = "NONE DETECTED"
        activity_badge = "badge-success"
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Thermal Anomaly</div>
            <div class="metric-value" style="font-size:1.35rem;">{activity_label}</div>
            <span class="metric-badge {activity_badge}">NASA FIRMS</span>
            <div style="font-size:0.75rem;color:#cbd5e1;margin-top:0.45rem;">{activity_text}</div>
        </div>
        """, unsafe_allow_html=True)

    # Card 3: historical archive match around the target (25 km configured radius).
    historical_count = int(historical.get("count", len(historical.get("events", [])) or
                                         (1 if historical.get("found") else 0)))
    historical_label = f"{historical_count} MATCH{'ES' if historical_count != 1 else ''}" if historical_count else "NO PRIOR INCIDENT"
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Historical Analysis</div>
            <div class="metric-value" style="font-size:1.15rem;">{historical_label}</div>
            <span class="metric-badge badge-info">Past Records</span>
            <div style="font-size:0.75rem;color:#cbd5e1;margin-top:0.45rem;">Curated archive; not exhaustive or live-fire status.</div>
        </div>
        """, unsafe_allow_html=True)

    # Card 4: severity for the representative FIRMS event, if real imagery was processed.
    sev_level = severity.get("severity_level") or "PENDING"
    if damage.get("available"):
        sev_label = str(sev_level).upper()
        sev_badge = "badge-danger" if any(x in sev_label for x in ("HIGH", "SEVERE")) else "badge-success"
        sev_detail = "Sentinel-2 assessment completed for selected event"
    elif detection_count:
        sev_label = "PENDING"
        sev_badge = "badge-warning"
        sev_detail = "Waiting for usable pre-fire/post-fire imagery"
    else:
        sev_label = "NOT ASSESSED"
        sev_badge = "badge-info"
        sev_detail = "No FIRMS event available to assess"
    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Assessed Severity</div>
            <div class="metric-value" style="font-size:1.3rem;">{sev_label}</div>
            <span class="metric-badge {sev_badge}">Post-fire assessment</span>
            <div style="font-size:0.75rem;color:#cbd5e1;margin-top:0.45rem;">{sev_detail}</div>
        </div>
        """, unsafe_allow_html=True)

    st.caption(
        "FWI is calculated for the selected coordinate. NASA FIRMS detections and the hotspot map "
        "continue to use the 100 km search radius. Historical Analysis uses the configured 25 km "
        "archive-matching radius. Sentinel-2 severity applies to the selected representative fire event."
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # TABBED DETAILED WORKSPACE
    # -------------------------------------------------------------------------
    tab_map, tab_env, tab_active, tab_sat, tab_rec = st.tabs([
        "📍 Geospatial Overview", 
        "🌤️ Risk & Weather", 
        "🔥 Hotspot Monitoring", 
        "🛰️ Sentinel-2 Assessment", 
        "📋 Action Plan"
    ])

    # --- TAB 1: GEOSPATIAL MAP ---
    with tab_map:
        st.subheader("Interactive Hotspot Map")
        st.caption(
            "Light CARTO basemap with NASA FIRMS thermal detections. "
            "Markers represent satellite observations, not individually confirmed wildfires."
        )

        active_records = res.get("active_fire", {}).get("all_nearby", []) or []
        intelligence = res.get("hotspot_intelligence", {}) or {}
        clusters = intelligence.get("clusters", []) or []

        map_view = st.radio(
            "Map display",
            ["Cluster view", "Individual detections"],
            horizontal=True,
            key="firesight_map_view",
        )

        map_data = [{
            "lat": float(lat),
            "lon": float(lon),
            "type": "Selected target",
            "details": f"Target coordinates: {float(lat):.4f}, {float(lon):.4f}",
            "color": [30, 136, 229, 230],
            "radius": 1100,
        }]

        if map_view == "Cluster view" and clusters:
            for cluster in clusters:
                count = int(cluster.get("hotspot_count") or 0)
                map_data.append({
                    "lat": float(cluster.get("latitude", lat)),
                    "lon": float(cluster.get("longitude", lon)),
                    "type": f"Hotspot cluster · {count} detections",
                    "details": (
                        f"Cluster {cluster.get('cluster_id', 'N/A')} | "
                        f"{count} detections | "
                        f"Observation count: {cluster.get('persistence_count', 'N/A')}"
                    ),
                    "color": [249, 115, 22, 210],
                    "radius": max(900, min(4500, 650 + count * 18)),
                })
        elif active_records:
            for point in active_records:
                try:
                    point_lat = float(point.get("latitude"))
                    point_lon = float(point.get("longitude"))
                except (TypeError, ValueError):
                    continue

                confidence = str(point.get("confidence", "")).lower()
                point_color = (
                    [220, 38, 38, 210] if confidence in ("h", "high")
                    else [245, 158, 11, 200]
                )
                map_data.append({
                    "lat": point_lat,
                    "lon": point_lon,
                    "type": "NASA FIRMS thermal detection",
                    "details": (
                        f"Confidence: {point.get('confidence', 'N/A')} | "
                        f"FRP: {point.get('frp', 'N/A')} MW | "
                        f"Satellite: {point.get('satellite', 'N/A')} | "
                        f"Date: {point.get('acq_date', 'N/A')} "
                        f"{point.get('acq_time', '')} UTC"
                    ),
                    "color": point_color,
                    "radius": 350,
                })

        map_df = pd.DataFrame(map_data)
        view_state = pdk.ViewState(
            latitude=float(lat),
            longitude=float(lon),
            zoom=8 if map_view == "Cluster view" else 10,
            pitch=0,
            bearing=0,
        )

        hotspot_layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position="[lon, lat]",
            get_fill_color="color",
            get_radius="radius",
            radius_min_pixels=4,
            radius_max_pixels=24,
            stroked=True,
            get_line_color=[255, 255, 255, 190],
            line_width_min_pixels=1,
            pickable=True,
            auto_highlight=True,
        )

        st.pydeck_chart(
            pdk.Deck(
                layers=[hotspot_layer],
                initial_view_state=view_state,
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                tooltip={"text": "{type}\\n{details}\\nLat: {lat}, Lon: {lon}"},
            ),
            use_container_width=True,
        )

        st.caption(
            f"Showing {len(map_data) - 1:,} "
            f"{'cluster centres' if map_view == 'Cluster view' and clusters else 'individual detections'} "
            f"plus the selected target. Switch to Individual detections to inspect every FIRMS record."
        )

    # --- TAB 2: ENVIRONMENT & RISK ---
    with tab_env:
        col_w, col_f = st.columns([1, 1])

        with col_w:
            st.subheader("Current Atmospheric Data")
            w = res['weather']
            
            w1, w2 = st.columns(2)
            w1.metric("🌡️ Temperature", f"{w['temperature']} °C")
            w2.metric("💧 Humidity", f"{w['humidity']} %")
            
            w3, w4 = st.columns(2)
            w3.metric("💨 Wind Speed", f"{w['wind_speed']} km/h")
            w4.metric("🌧️ Rainfall", f"{w['rainfall']} mm")

        with col_f:
            st.subheader("Canadian Fire Weather Index (FWI)")
            risk = res.get("wildfire_risk", {})
            fwi = risk.get("fwi", {}) or {}
            if fwi.get("available"):
                comp = fwi.get("components", {})
                fwi_value = comp.get("FWI")
                fwi_text = f"{float(fwi_value):.2f}" if isinstance(fwi_value, (int, float)) else "N/A"
                st.metric("FWI value", f"{fwi_text} · {risk.get('level', '')}")
                st.caption("FWI is a fire-weather danger index, not the probability that a fire will occur.")
                st.info(
                    "Interpretation: FWI describes how conducive the current weather is to fire "
                    "ignition and spread. It does not confirm whether a wildfire exists. NASA FIRMS "
                    "thermal detections are shown separately in the Hotspot Monitoring tab."
                )
                component_rows = [
                    {"FWI component": "FFMC — fine fuel moisture", "Value": comp.get("FFMC")},
                    {"FWI component": "DMC — duff moisture", "Value": comp.get("DMC")},
                    {"FWI component": "DC — drought code", "Value": comp.get("DC")},
                    {"FWI component": "ISI — initial spread index", "Value": comp.get("ISI")},
                    {"FWI component": "BUI — buildup index", "Value": comp.get("BUI")},
                    {"FWI component": "FWI — fire weather index", "Value": fwi_text},
                ]
                st.dataframe(pd.DataFrame(component_rows), hide_index=True, use_container_width=True)
                history = fwi.get("history", [])
                if history:
                    st.markdown("##### Recent FWI calculation history")
                    st.dataframe(pd.DataFrame(history), hide_index=True, use_container_width=True)
                st.caption(f"Weather history source: {w.get('fwi_history_source', 'Open-Meteo')}")
                st.caption(w.get("fwi_history_method", "Daily weather aggregates used as proxy inputs."))
                st.warning(fwi.get("initialization", "Initial moisture codes are provisional."))
            else:
                st.warning("FWI unavailable — a valid multi-day weather history is required.")
                st.caption(fwi.get("reason", "No weather-history data was returned."))
                st.info("The dashboard deliberately does not fall back to an arbitrary weighted score.")

            # Regional FWI: separate from the selected-coordinate FWI and FIRMS detections.
            regional = res.get("regional_fwi", {}) or {}
            st.markdown("---")
            st.subheader("🌍 Regional Fire Weather Index — 100 km")
            st.caption("FWI is calculated independently at sampled locations within 100 km of the target.")
            if regional.get("available"):
                r1, r2, r3 = st.columns(3)
                r1.metric("Regional average FWI", f"{regional['average_fwi']:.2f}", regional.get("average_level", ""))
                r2.metric("Maximum regional FWI", f"{regional['maximum_fwi']:.2f}", regional.get("maximum_level", ""))
                r3.metric("Successful grid cells", f"{regional.get('successful_cells', 0)}/{regional.get('grid_size', 0)}")
                high = regional["highest_risk_cell"]
                st.write(f"**Highest-risk sampled cell:** {high['label']} · "
                         f"{high['latitude']:.4f}, {high['longitude']:.4f} · "
                         f"{high['distance_from_target_km']} km from target")
                rows = []
                for cell in regional.get("cells", []):
                    result = cell.get("fwi", {})
                    if result.get("available"):
                        rows.append({"Grid cell": cell["label"],
                                     "Latitude": round(cell["latitude"], 4),
                                     "Longitude": round(cell["longitude"], 4),
                                     "Distance (km)": cell["distance_from_target_km"],
                                     "FWI": result["score"], "Danger level": result["level"]})
                if rows:
                    df_region = pd.DataFrame(rows)
                    st.dataframe(df_region, hide_index=True, use_container_width=True)
                    fig_region = px.scatter(
                        df_region, x="Longitude", y="Latitude", color="FWI", size="FWI",
                        hover_name="Grid cell", hover_data=["Distance (km)", "Danger level"],
                        color_continuous_scale=["#16a34a", "#eab308", "#f97316", "#dc2626"],
                        title="Regional FWI sample grid"
                    )
                    fig_region.update_layout(height=360)
                    st.plotly_chart(fig_region, use_container_width=True)
                st.caption(regional.get("method", ""))
                st.warning(regional.get("limitation", "Regional FWI is an experimental estimate."))
                if regional.get("failed_cells"):
                    with st.expander("Grid cells with data errors"):
                        st.json(regional["failed_cells"])
            else:
                st.warning("Regional FWI unavailable.")
                st.caption(regional.get("reason", "No regional weather history was returned."))

            provider = w.get("provider", "Unknown weather provider")
            st.caption(f"Current weather source: {provider} · Live data: {'Yes' if w.get('is_live') else 'No / fallback'}")
            validation = w.get("validation", {}) or {}
            quality = risk.get("data_quality", "UNKNOWN")
            if quality == "LOW":
                st.error(f"Weather data quality: {quality} — verify readings before relying on this index.")
            elif quality == "CHECK RECOMMENDED":
                st.warning(f"Weather data quality: {quality}")
            else:
                st.info(f"Weather data quality: {quality}")
            st.caption(f"Current-condition cross-check: {validation.get('status', 'not performed')}")
            with st.expander("How to interpret weather validation"):
                st.write(
                    "The dashboard reports the weather provider, whether the reading is live, "
                    "and any available cross-check against Open-Meteo. A cross-check is a "
                    "sanity check, not a guarantee that either provider is perfectly accurate."
                )
                st.write(
                    "FWI also depends on accumulated weather history and moisture-code "
                    "initialization. If the dashboard labels initialization as provisional, "
                    "treat the index as an estimate rather than a fully locally calibrated value."
                )
            if validation.get("secondary_readings"):
                st.markdown("##### OpenWeatherMap vs Open-Meteo cross-check")
                secondary = validation["secondary_readings"]
                comparison = pd.DataFrame([
                    {"Measurement": "Temperature (°C)", "Primary": w.get("temperature"), "Open-Meteo": secondary.get("temperature")},
                    {"Measurement": "Humidity (%)", "Primary": w.get("humidity"), "Open-Meteo": secondary.get("humidity")},
                    {"Measurement": "Wind (km/h)", "Primary": w.get("wind_speed"), "Open-Meteo": secondary.get("wind_speed")},
                ])
                st.dataframe(comparison, hide_index=True, use_container_width=True)
                if validation.get("differences"):
                    st.caption("Absolute differences: " + " · ".join(f"{k.replace('_', ' ')}: {v}" for k, v in validation["differences"].items()))
            for warning in risk.get("warnings", []):
                st.warning(warning)
            st.caption(risk.get("score_type", "FWI fire-weather danger index; not a calibrated fire probability."))

    # --- TAB 3: ACTIVE DETECTION ---
    with tab_active:
        st.subheader("NASA FIRMS Active Thermal Anomaly Detection · 100 km radius")
        st.info(res['active_fire']['status_message'])

        if res['active_fire']['detected']:
            df_active = pd.DataFrame(res['active_fire']['all_nearby'])
            st.markdown("##### Detected Thermal Points")
            st.dataframe(df_active, use_container_width=True)

            intelligence = res.get("hotspot_intelligence", {})
            assessments = intelligence.get("assessments", [])
            if assessments:
                st.markdown("##### Context-aware Investigation Priority")
                st.caption(intelligence.get("score_note", "Scores prioritize review; they are not calibrated probabilities."))
                rows = []
                for item in assessments:
                    hotspot = item.get("hotspot", {})
                    assessment = item.get("assessment", {})
                    rows.append({
                        "Latitude": hotspot.get("latitude"),
                        "Longitude": hotspot.get("longitude"),
                        "Confidence": hotspot.get("confidence"),
                        "Priority score": assessment.get("score"),
                        "Priority": assessment.get("level"),
                        "Decision": assessment.get("decision"),
                        "Reasons": "; ".join(assessment.get("reasons", [])),
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

            clusters = intelligence.get("clusters", [])
            if clusters:
                st.markdown("##### Nearby Hotspot Clusters & Persistence")
                st.caption("Clusters are distance-based summaries of the current FIRMS response; repeated times indicate persistence in the supplied records.")
                cluster_rows = [{
                    "Cluster": c.get("cluster_id"), "Latitude": round(c.get("latitude", 0), 4),
                    "Longitude": round(c.get("longitude", 0), 4), "Hotspots": c.get("hotspot_count"),
                    "Observation times": c.get("persistence_count"), "First observed": c.get("first_observed"),
                    "Last observed": c.get("last_observed")
                } for c in clusters]
                st.dataframe(pd.DataFrame(cluster_rows), use_container_width=True)

            # DSA demonstration: graph adjacency list + heap-based priority queue.
            graph_summary = intelligence.get("graph_summary", {})
            queue_rows = intelligence.get("priority_queue", [])
            st.markdown("##### DSA: Graph Connections & Priority Queue")
            st.caption("Clusters are graph nodes; edges connect cluster centers within the configured radius. A max-priority queue (implemented with Python's min-heap using negative scores) ranks clusters for review.")
            st.write(f"Graph: {graph_summary.get('nodes', 0)} nodes · {graph_summary.get('edges', 0)} edges · maximum degree {graph_summary.get('max_degree', 0)}")
            if queue_rows:
                st.dataframe(pd.DataFrame(queue_rows), use_container_width=True)
        else:
            st.success("No high-confidence thermal anomalies registered in target buffer zone.")
            st.info("Context-aware scoring and clustering appear here when FIRMS returns hotspot records.")

    # --- TAB 4: SATELLITE DAMAGE ASSESSMENT ---
    with tab_sat:
        st.subheader("Sentinel-2 Post-Fire Assessment (NBR Analysis)")
        
        if res['damage_assessment']['available']:
            bm = res['damage_assessment']['burn_metrics']
            
            b1, b2 = st.columns(2)
            b1.metric("Estimated Burned Area (Hectares)", f"{bm['burned_area_ha']} ha")
            b2.metric("Estimated Burned Area (Km²)", f"{bm['burned_area_km2']} km²")

            st.markdown("##### Severity Proportions")
            proportions = bm.get('severity_proportions', {})
            if proportions:
                df_prop = pd.DataFrame(list(proportions.items()), columns=["Severity Tier", "Proportion"])
                fig_pie = px.pie(
                    df_prop, 
                    names="Severity Tier", 
                    values="Proportion", 
                    hole=0.4,
                    color_discrete_sequence=px.colors.sequential.OrRd_r
                )
                fig_pie.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0), template="plotly_dark")
                st.plotly_chart(fig_pie, use_container_width=True)
            
            st.markdown("##### Satellite image provenance")
            da = res["damage_assessment"]
            st.write(f"Source: {da.get('satellite_source', 'Copernicus Sentinel-2 L2A')}")
            st.write(f"Pre-fire acquisition: {da.get('pre_scene', {}).get('date', 'Unknown')} · "
                     f"cloud cover: {da.get('pre_scene', {}).get('cloud_cover', 'Unknown')}%")
            st.write(f"Post-fire acquisition: {da.get('post_scene', {}).get('date', 'Unknown')} · "
                     f"cloud cover: {da.get('post_scene', {}).get('cloud_cover', 'Unknown')}%")
            st.caption(da.get("note", "Derived from satellite reflectance bands."))
            st.markdown("##### Vegetation change")
            vm = da.get("vegetation_metrics", {})
            if vm:
                v1, v2, v3 = st.columns(3)
                v1.metric("Pre-fire NDVI", vm.get("pre_fire_ndvi_mean"))
                v2.metric("Post-fire NDVI", vm.get("post_fire_ndvi_mean"))
                v3.metric("Vegetation loss", f"{vm.get('vegetation_loss_percentage')}%")
            st.markdown("##### Infrastructure Vulnerability")
            st.info(res['damage_assessment']['infrastructure_metrics']['status_message'])
        else:
            st.info("🛰️ Post-fire damage assessment: NOT AVAILABLE — no verified Sentinel-2 image pair was processed.")
            st.warning(res['damage_assessment'].get('reason', 'Damage assessment unavailable.'))
            da = res.get("damage_assessment", {}) or {}
            selected = da.get("selected_event")
            if selected:
                st.markdown("##### FIRMS event selected for Sentinel-2")
                st.dataframe(pd.DataFrame([selected]), hide_index=True, use_container_width=True)
            if da.get("pre_date_range") or da.get("post_date_range"):
                st.caption(
                    f"Pre-fire search: {da.get('pre_date_range', 'N/A')} · "
                    f"Post-fire search: {da.get('post_date_range', 'N/A')}"
                )
            if da.get("pre_scene_count") is not None or da.get("post_scene_count") is not None:
                d1, d2 = st.columns(2)
                d1.metric("Pre-fire scenes found", da.get("pre_scene_count", 0))
                d2.metric("Post-fire scenes found", da.get("post_scene_count", 0))
            attempts = da.get("candidate_attempts", [])
            if attempts:
                st.markdown("##### FIRMS events tested for Sentinel-2")
                st.dataframe(pd.DataFrame(attempts), hide_index=True, use_container_width=True)
            diagnostics = da.get("diagnostics")
            if diagnostics:
                with st.expander("Sentinel-2 technical diagnostics"):
                    st.json(diagnostics)
            if res['active_fire'].get('detected'):
                st.caption("A FIRMS hotspot was found, but a suitable pre-fire/post-fire Sentinel-2 pair may be missing or the API connection may need attention.")
            else:
                st.caption("No active FIRMS hotspot was found, so the automatic post-fire assessment was not started.")
            hist = res.get("historical_match", {})
            if hist.get("found"):
                st.markdown("**Archived historical context (separate from current FIRMS activity):**")
                for archived in hist.get("events", []):
                    st.write(f"{archived.get('fire_name')} · {archived.get('event_date')} · {archived.get('distance_km')} km from target.")
                st.caption("The built-in archive is curated and incomplete. No archive match does not mean no wildfire occurred.")

    # --- TAB 5: ACTION PLAN ---
    with tab_rec:
        st.subheader("Automated Recovery Protocols")
        rec = res['recovery']
        
        prio = rec.get('recovery_priority')
        if prio:
            prio_color = "#ef4444" if "HIGH" in str(prio).upper() else "#f59e0b"
            st.markdown(f"#### Priority Level: <span style='color:{prio_color};'>{prio}</span>", unsafe_allow_html=True)
            
            st.markdown("##### Recommended Action Steps:")
            for idx, r in enumerate(rec.get('recommendations', []), 1):
                st.markdown(f"**{idx}.** {r}")
        else:
            st.info("No recovery priority has been assigned because verified post-fire damage data is unavailable.")
            st.caption("Weather-based risk is shown separately and should not be interpreted as confirmed fire damage.")

else:
    st.info(" Select execution mode in the sidebar and click **Run Intelligence Pipeline** to start.")