"""Phase 6: Local Streamlit dashboard. Launch from project root using PowerShell.

    python -m streamlit run dashboard.py --server.address 127.0.0.1
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from logistics.analytics import DEFAULT_DB, get_filters, load_dashboard
from logistics.assistant import QUESTIONS, explain, local_ollama_explanation

st.set_page_config(page_title='Global Logistics | Local Analytics', page_icon='🚢', layout='wide')
st.title('🚢 Global Logistics | Local Analytics')
st.caption('Portfolio demonstration · Synthetic shipment data · Read-only DuckDB · Runs on your PC · No paid cloud services')

if not DEFAULT_DB.is_file():
    st.error('Warehouse not found. Run `python -m logistics.warehouse build` first.')
    st.stop()

try:
    options = get_filters(DEFAULT_DB)
except Exception as exc:
    st.error(f'Unable to open the warehouse: {exc}')
    st.stop()

with st.sidebar:
    st.header('Shipment filters')
    carrier_options = ['All carriers'] + options['carriers']
    selected_carrier = st.selectbox('Carrier', carrier_options)
    route_lookup = {route['label']: route['route_key'] for route in options['routes']}
    route_label = st.selectbox('Route', ['All routes'] + list(route_lookup))
    carrier = None if selected_carrier == 'All carriers' else selected_carrier
    route_key = route_lookup.get(route_label)
    st.divider()
    st.caption('All charts and assistant answers follow these filters.')
    st.caption('Close the PowerShell process with Ctrl+C when finished.')

try:
    snapshot = load_dashboard(DEFAULT_DB, carrier, route_key)
except Exception as exc:
    st.error(f'Could not compute warehouse metrics: {exc}')
    st.stop()

quality_file = Path('data/monitor/quality_report.json')
if quality_file.is_file():
    try:
        report = json.loads(quality_file.read_text(encoding='utf-8'))
        quality_status = report.get('status', 'UNKNOWN')
        if quality_status != 'PASS':
            st.warning(f'Last Phase 5 quality gate: {quality_status}. Review data/monitor/quality_report.json.')
        else:
            st.caption('Last saved Phase 5 quality gate: PASS (not continuously checked).')
    except (ValueError, OSError):
        st.warning('The saved Phase 5 quality report is unreadable.')
else:
    st.warning('No saved quality report. Run `python -m logistics.quality_monitor check`.')

s = snapshot['overview']
cols = st.columns(5)
for col, label, value in zip(cols,
    ('Total shipments', 'Delivered', 'Late deliveries', 'Customs holds', 'On-time of delivered'),
    (s['shipments'], s['delivered'], s['late'], s['customs_holds'],
     'N/A' if s['on_time_pct'] is None else f"{s['on_time_pct']:.2f}%")):
    col.metric(label, value)

tab_dashboard, tab_exceptions, tab_assistant = st.tabs(['Performance', 'Exceptions', 'Analytics assistant'])
with tab_dashboard:
    left, right = st.columns(2)
    with left:
        st.subheader('Carrier performance')
        st.dataframe(pd.DataFrame(snapshot['carriers']), hide_index=True, use_container_width=True)
        if snapshot['carriers']:
            st.bar_chart(pd.DataFrame(snapshot['carriers']).set_index('carrier')[['shipments', 'late']])
    with right:
        st.subheader('Latest shipment status')
        if snapshot['status_distribution']:
            st.bar_chart(pd.DataFrame(snapshot['status_distribution']).set_index('status')['shipments'])
        else:
            st.info('No shipments match these filters.')
    st.subheader('Route performance')
    st.dataframe(pd.DataFrame(snapshot['routes']), hide_index=True, use_container_width=True)
    st.subheader('Daily event volumes')
    if snapshot['daily_events']:
        timeline = pd.DataFrame(snapshot['daily_events'])
        timeline['event_date'] = pd.to_datetime(timeline['event_date'])
        st.line_chart(timeline.set_index('event_date')['events'])
    else:
        st.info('No events match these filters.')
with tab_exceptions:
    st.subheader('Delay labels')
    st.caption('Distinct affected shipments per recorded reason. A shipment may have multiple reasons.')
    if snapshot['delay_reasons']:
        st.bar_chart(pd.DataFrame(snapshot['delay_reasons']).set_index('delay_reason')['affected_shipments'])
    else:
        st.info('No delay reasons were recorded in this selection.')
    st.subheader('Shipment exceptions (up to 100)')
    st.dataframe(pd.DataFrame(snapshot['exceptions']), hide_index=True, use_container_width=True)
with tab_assistant:
    st.subheader('Ask about your logistics metrics')
    st.caption('Default: deterministic answers from warehouse results. It does not invent SQL or contact an online model.')
    q = st.selectbox('Example question', QUESTIONS + ('Enter my own question',))
    question = st.text_input('Question', value='' if q == 'Enter my own question' else q)
    use_ollama = st.checkbox('Optional: explain with Ollama running locally on this computer', value=False)
    model = st.text_input('Installed local model', value='llama3.2:1b') if use_ollama else None
    if st.button('Answer', type='primary'):
        result = explain(question, snapshot)
        st.markdown('**Verified metric answer**')
        st.write(result['answer'])
        if result['evidence']:
            with st.expander('Show exact supporting metrics'):
                st.json(result['evidence'])
        if use_ollama and result['intent'] != 'unsupported':
            try:
                st.markdown('**Optional local model explanation (check against the verified metrics)**')
                st.write(local_ollama_explanation(question, result, model))
            except (RuntimeError, ValueError) as exc:
                st.info(str(exc))

st.divider()
st.caption('All values are synthetic project data, not Amazon operational data. Data is read from the local warehouse only.')
