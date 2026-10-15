# Multi-reference Allele Comparison

Install Python 3.11 or later, then from this directory run:

On Windows, you can double-click `Install Dependencies.cmd` once, then `Start App.cmd` each time you want to use the app. These launchers use the standard Windows Python launcher (`py`).

```
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Supports GeneMapper CSV/TXT repeated Marker/Allele groups and ArmedXpert-style wide XLS/XLSX/CSV/TSV tables. Excel imports read the first worksheet. Wide tables require sample IDs in the first column and locus headers in the first row. Other arrangements require conversion before import; automatic custom column mapping is not included in this version.

Assign Reference, Mixture, or Ignore to each imported row, then configure contributor counts and reference selections per mixture. Reference counts have no imposed application limit. Profiles can be selected across files. Selecting references does not assume they contributed, so no unknown-contributor count is inferred and reference selections must fit the entered contributor count.

Excluded from comparisons: IQCS, IQCL, QS1, QS2, amelogenin aliases AMEL/Amel, Yindel, and Y/DYS marker names. Raw excluded calls remain in Import_Audit. Numeric OL suffixes are removed for matching; unresolved labels generate warnings and require acknowledgement before comparison. Blank cells indicate no call. A single allele is counted once, without inferred dosage. Counts count locus–allele pairs, not unique labels across the whole profile.

For each reference: observed = evidence intersection reference; missing = reference minus evidence; unique = reference minus union of other selected references. Overall recovery divides observed by all reference calls. Unique recovery divides observed unique calls by expected unique calls. Zero denominators produce blank values. Shared evidence calls match at least two selected references and count once in mixture totals. Foreign calls match no selected reference. These comparisons do not infer biological attribution, dropout, stutter, or contributor compatibility.

Excel contains Master_Summary, per-mixture PL and ALLELES sheets, Reference_Summary, Assignments mapping R1/R2/etc. to full sample identities, Import_Audit, and Import_Warnings. Sheet numbers prevent collisions from long sample names. Duplicate sample labels remain separate through source-and-row IDs. Inputs are never modified.

Master_Summary contains mixture identifiers and contributor reference names, followed by a seven-column block per contributor: observed, expected, missing, unique_observed, unique_expected, recovery, unique_recovery. Recovery = observed / expected. Unique recovery = unique_observed / unique_expected. Both are percentages; zero denominators are blank. Foreign/shared counts and detail-sheet names follow. Slots follow reference-selection order and expand with the largest entered mixture contributor count in the workbook. Distinct alleles at each locus count once, including homozygotes. Sex-linked and quality markers remain excluded. Master_Summary is the first sheet; Reference_Summary is second.

Report slots follow the entered mixture contributor count. Names beginning with a positive integer followed by an underscore (for example 3_ or 5_) supply the initial editable contributor count; other names start at 2. This is a naming hint, not an estimate from allele peaks. Unreferenced contributors have blank names and metrics.

Configure mixtures includes bulk selection: choose multiple mixtures, a contributor count, and reference profiles, then Apply settings to selected mixtures. This replaces both settings only on selected mixtures; individual controls remain editable afterward.
