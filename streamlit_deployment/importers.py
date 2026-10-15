"""Read-only importers retaining source labels and excluded markers."""
import csv
import hashlib
import io
import re
from core import Sample, allele, excluded

def _sample(source, data, row, name):
    digest = hashlib.sha256(data).hexdigest()[:16]
    s = Sample(f'{source}:{digest}:{row}', str(name).strip() or f'Unnamed row {row}', source, row)
    if re.search(r'ladder|allelic|\bAL\b|negative|positive|hidi', s.name, re.I):
        s.suggested_role = 'Ignore'
    return s

def _add(s, locus, cells):
    locus = str(locus).strip()
    locus = 'vWA' if locus.upper() == 'VWA' else locus.upper()
    if not locus:
        if any(str(c).strip() for c in cells):
            s.warnings.append('Allele data without a marker name')
        return
    raw = [str(c).strip() for c in cells]
    if locus in s.raw:
        s.warnings.append(f'Duplicate marker {locus}; calls combined')
    s.raw.setdefault(locus, []).extend(raw)
    if excluded(locus):
        return
    values = s.profiles.setdefault(locus, set())
    for cell in raw:
        for token in cell.split(','):
            try:
                value = allele(token)
                if value is not None:
                    values.add(value)
            except ValueError as error:
                s.warnings.append(f'{locus}: {error}')

def parse(source, data):
    ext = source.rsplit('.', 1)[-1].lower()
    if ext in ('csv', 'txt', 'tsv'):
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = data.decode('cp1252')
        try:
            dialect = csv.Sniffer().sniff(text[:16000], delimiters=',\t;')
        except csv.Error:
            dialect = csv.excel_tab if ext in ('txt', 'tsv') else csv.excel
        rows = list(csv.reader(io.StringIO(text), dialect))
    elif ext == 'xls':
        import xlrd
        book = xlrd.open_workbook(file_contents=data)
        sheet = book.sheet_by_index(0)
        rows = [sheet.row_values(i) for i in range(sheet.nrows)]
    elif ext == 'xlsx':
        import openpyxl
        book = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        rows = [[v if v is not None else '' for v in row] for row in book.worksheets[0].iter_rows(values_only=True)]
        book.close()
    else:
        raise ValueError('Supported files: CSV, TXT, TSV, XLS, XLSX')
    if len(rows) < 2:
        raise ValueError('No sample rows found')
    header = [str(v).strip() for v in rows[0]]
    lower = [v.lower() for v in header]
    starts = [i for i, v in enumerate(lower) if v == 'marker']
    gene = bool(starts and 'sample name' in lower)
    if not gene and any(v in ('marker', 'locus') for v in lower[1:]):
        raise ValueError('This looks like a long profile table. Convert to one sample per row and one locus per column for this version.')
    samples = []
    for rownum, row in enumerate(rows[1:], 2):
        if not any(str(v).strip() for v in row):
            continue
        if gene:
            name = row[lower.index('sample name')]
        else:
            name = row[0]
        s = _sample(source, data, rownum, name)
        if gene:
            if len(row) != len(header):
                s.warnings.append(f'Row has {len(row)} fields; header has {len(header)}')
            row = list(row) + [''] * max(0, len(header)-len(row))
            s.raw['_Sample File'] = [str(row[lower.index('sample file')])] if 'sample file' in lower else []
            if any('ladder' in x.lower() for x in s.raw['_Sample File']):
                s.suggested_role = 'Ignore'
            for b, start in enumerate(starts):
                end = starts[b+1] if b+1 < len(starts) else len(header)
                cols = [i for i in range(start+1, end) if re.fullmatch(r'allele\s+\d+', lower[i])]
                _add(s, row[start], [row[i] for i in cols])
        else:
            for i, locus in enumerate(header[1:], 1):
                _add(s, locus, [row[i] if i < len(row) else ''])
        if not any(s.profiles.values()):
            s.warnings.append('No autosomal allele calls after exclusions')
        samples.append(s)
    return samples, 'GeneMapper repeated groups' if gene else 'Wide profile table'
