import hashlib
import re
import importlib
from pathlib import Path
import pandas as pd
import streamlit as st
from importers import parse
from core import compare
import reports

# Streamlit reruns must use the current exporter, including in existing sessions.
importlib.reload(reports)
export = reports.export
REPORT_VERSION = hashlib.sha256(Path(reports.__file__).read_bytes()).hexdigest()

st.set_page_config(page_title='Multi-reference Allele Comparison', layout='wide')
st.title('Multi-reference Allele Comparison')
st.write('Upload profiles, identify references and mixtures, and choose the references to compare with each mixture.')
uploads = st.file_uploader('Profile files', type=['csv', 'txt', 'tsv', 'xls', 'xlsx'], accept_multiple_files=True)
if not uploads:
    st.stop()
samples, failed = [], False
seen = set()
for upload in uploads:
    data = upload.getvalue()
    identity = (upload.name, hashlib.sha256(data).hexdigest())
    if identity in seen:
        st.info(f'Duplicate upload skipped: {upload.name}')
        continue
    seen.add(identity)
    try:
        parsed, layout = parse(upload.name, data)
        samples.extend(parsed)
        st.caption(f'{upload.name}: {layout}, {len(parsed)} samples')
    except Exception as error:
        st.error(f'{upload.name}: {error}')
        failed = True
if failed:
    st.warning('Remove or correct files that failed to import before comparing.')
    st.stop()
st.subheader('1. Assign sample roles')
table_id = hashlib.sha256(''.join(s.id for s in samples).encode()).hexdigest()
table_key = 'role_table_' + table_id
revision_key = 'role_revision_' + table_id
if table_key not in st.session_state:
    st.session_state[table_key] = pd.DataFrame([
        {'Select': False, 'ID': s.id, 'Sample': s.name, 'Source': s.source,
         'Role': s.suggested_role, 'Warnings': '; '.join(s.warnings)} for s in samples])
    st.session_state[revision_key] = 0
st.caption('Check samples in the Select column, choose a role below, then apply it to all selected samples.')
roles = st.data_editor(st.session_state[table_key],
                       disabled=['ID', 'Sample', 'Source', 'Warnings'], hide_index=True,
                       column_config={'Select': st.column_config.CheckboxColumn('Select', default=False),
                                      'ID': None,
                                      'Role': st.column_config.SelectboxColumn(options=['Reference', 'Mixture', 'Ignore'], required=True)},
                       key=f'roles_{table_id}_{st.session_state[revision_key]}')
selected_count = int(roles['Select'].sum())
st.caption(f'{selected_count} sample(s) selected')
all_col, clear_col, role_col, apply_col = st.columns([1, 1, 2, 2])
select_all = all_col.button('Select all samples')
clear_selection = clear_col.button('Clear selection')
bulk_role = role_col.selectbox('Role for selected samples', ['Reference', 'Mixture', 'Ignore'])
apply_role = apply_col.button('Apply role to selected', disabled=selected_count == 0)
if select_all or clear_selection or apply_role:
    updated = roles.copy()
    if apply_role:
        updated.loc[updated['Select'], 'Role'] = bulk_role
    else:
        updated['Select'] = bool(select_all)
    st.session_state[table_key] = updated
    st.session_state[revision_key] += 1
    st.rerun()
lookup = {s.id: s for s in samples}
refs = [lookup[row.ID] for row in roles.itertuples() if row.Role == 'Reference']
mixtures = [lookup[row.ID] for row in roles.itertuples() if row.Role == 'Mixture']
st.subheader('2. Configure mixtures')
st.caption('Selected references are evaluated profiles. Their selection does not establish contributor status.')
with st.expander('Apply settings to multiple mixtures', expanded=False):
    bulk_mixtures = st.multiselect(
        'Mixtures to update', options=[s.id for s in mixtures],
        format_func=lambda x: f'{lookup[x].name} — {lookup[x].source}, row {lookup[x].row}',
        key='bulk_mixtures_' + table_id)
    bulk_count = st.number_input('Contributor count to apply', min_value=1, value=2, step=1,
                                 key='bulk_count_' + table_id)
    bulk_references = st.multiselect(
        'References to apply', options=[r.id for r in refs],
        format_func=lambda x: f'{lookup[x].name} — {lookup[x].source}, row {lookup[x].row}',
        key='bulk_references_' + table_id)
    st.caption('Apply replaces both settings for the selected mixtures. You can adjust each mixture individually below.')
    if len(bulk_references) > bulk_count:
        st.warning('Select no more references than the contributor count.')
    if st.button('Apply settings to selected mixtures',
                 disabled=not bulk_mixtures or len(bulk_references) > bulk_count):
        for sample_id in bulk_mixtures:
            st.session_state['n_' + sample_id] = int(bulk_count)
            st.session_state['r_' + sample_id] = list(bulk_references)
            st.session_state['ack_' + sample_id] = False
        st.success(f'Updated {len(bulk_mixtures)} mixture(s). Individual controls below show the applied settings.')
jobs = []
for ev in mixtures:
    with st.expander(f'{ev.name} — {ev.source}, row {ev.row}', expanded=len(mixtures)<4):
        inferred_count = re.match(r'^([1-9]\d*)_', ev.name)
        initial_count = int(inferred_count.group(1)) if inferred_count else 2
        if 'n_' + ev.id not in st.session_state:
            st.session_state['n_' + ev.id] = initial_count
        count = st.number_input('Number of contributors', min_value=1, step=1, key='n_'+ev.id)
        if inferred_count:
            st.caption('Starting contributor count comes from the sample-name prefix. Confirm or edit it above.')
        selected = st.multiselect('References for this mixture', options=[r.id for r in refs],
                                  format_func=lambda x: f'{lookup[x].name} — {lookup[x].source}, row {lookup[x].row}', key='r_'+ev.id)
        if len(selected) > count:
            st.error('Selected references exceed the contributor count. Increase the count or select fewer references.')
        acknowledge = True
        if ev.warnings or any(lookup[x].warnings for x in selected):
            st.warning('This comparison includes import warnings. Review the warning column before running.')
            acknowledge = st.checkbox('I reviewed these import warnings', key='ack_'+ev.id)
        jobs.append((ev, [lookup[x] for x in selected], int(count), acknowledge))
if not mixtures:
    st.info('Designate at least one mixture.')
    st.stop()
signature = REPORT_VERSION + repr([(e.id, [r.id for r in rs], n, ack) for e, rs, n, ack in jobs])
report_name = st.text_input('Report name', value='allele_comparison_results',
                            help='Enter a filename. The .xlsx extension is added automatically.')
safe_report_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', report_name.strip())
if safe_report_name.lower().endswith('.xlsx'):
    safe_report_name = safe_report_name[:-5]
safe_report_name = safe_report_name.strip(' .')[:150] or 'allele_comparison_results'
if re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]', safe_report_name.split('.')[0], flags=re.I):
    safe_report_name = '_' + safe_report_name
if st.button('Compare and prepare Excel report', type='primary'):
    if any(len(rs) > n for _, rs, n, _ in jobs):
        st.error('Resolve reference selections that exceed contributor counts before exporting.')
    elif not all(j[3] for j in jobs):
        st.error('Review and acknowledge import warnings for each affected mixture.')
    else:
        ready = [(e, r, n) for e, r, n, _ in jobs]
        with st.spinner('Preparing comparisons…'):
            report = export(ready, samples)
        st.session_state['result'] = (signature, report)
saved = st.session_state.get('result')
if saved and saved[0] == signature:
    st.download_button('Download comparison results', saved[1], safe_report_name + '.xlsx',
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    for ev, references, _, _ in jobs:
        with st.expander(ev.name):
            details, attribution, totals, _, _ = compare(ev, references)
            st.dataframe(pd.DataFrame(totals), hide_index=True)
            st.dataframe(pd.DataFrame(details), hide_index=True)
            st.dataframe(pd.DataFrame(attribution), hide_index=True)
