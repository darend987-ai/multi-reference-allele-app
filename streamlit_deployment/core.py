"""Format-independent allele comparison. No contributor attribution is inferred."""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import re

EXCLUDED = {'iqcs', 'iqcl', 'qs1', 'qs2', 'amel', 'amelogenin', 'yindel'}

def excluded(locus):
    key = re.sub(r'[\s_-]+', '', str(locus)).lower()
    return key in EXCLUDED or key.startswith(('dys', 'y'))

def allele(raw):
    text = str(raw).strip()
    if text.lower() in ('', '-', 'nan', 'none'):
        return None
    text = re.sub(r'\s+OL$', '', text, flags=re.I).strip()
    if not re.fullmatch(r'\d+(?:\.\d+)?', text):
        raise ValueError(f'Unresolved allele label: {raw!r}')
    d = Decimal(text)
    return format(d.normalize(), 'f')

def sort_alleles(values):
    return sorted(values, key=Decimal)

def display(values):
    return ', '.join(sort_alleles(values)) or '-'

@dataclass
class Sample:
    id: str
    name: str
    source: str
    row: int
    profiles: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    suggested_role: str = 'Mixture'

def compare(evidence, references):
    loci = sorted(set(evidence.profiles).union(*(set(r.profiles) for r in references)))
    details, attribution = [], []
    totals = {r.id: dict(reference=r.name, reference_id=r.id, observed=0, expected=0,
                        missing=0, unique_observed=0, unique_expected=0) for r in references}
    foreign_count = shared_count = 0
    for locus in loci:
        e = evidence.profiles.get(locus, set())
        sets = {r.id: r.profiles.get(locus, set()) for r in references}
        union = set().union(*sets.values())
        foreign = e - union
        shared = {a for a in e if sum(a in v for v in sets.values()) > 1}
        row = {'Locus': locus, 'Evidence Alleles': display(e),
               'Shared Alleles': display(shared), 'Foreign Alleles': display(foreign),
               'Shared Count': len(shared), 'Foreign Count': len(foreign)}
        foreign_count += len(foreign)
        shared_count += len(shared)
        for index, r in enumerate(references, 1):
            values = sets[r.id]
            others = set().union(*(v for k, v in sets.items() if k != r.id))
            unique = values - others
            observed, missing = e & values, values - e
            prefix = f'R{index}'
            row.update({f'{prefix} Alleles': display(values),
                        f'{prefix} Observed': display(observed), f'{prefix} Missing': display(missing),
                        f'{prefix} Unique Observed': display(e & unique),
                        f'{prefix} Observed Count': len(observed), f'{prefix} Missing Count': len(missing)})
            t = totals[r.id]
            for key, n in [('observed', len(observed)), ('expected', len(values)),
                           ('missing', len(missing)), ('unique_observed', len(e & unique)),
                           ('unique_expected', len(unique))]:
                t[key] += n
        for a in sort_alleles(e):
            matches = [f'R{i}' for i, r in enumerate(references, 1) if a in sets[r.id]]
            attribution.append({'Locus': locus, 'Allele': a, 'Matching References': ', '.join(matches),
                                'Classification': 'Foreign' if not matches else 'Shared' if len(matches)>1 else 'Reference-supported'})
        details.append(row)
    for t in totals.values():
        t['recovery'] = t['observed']/t['expected'] if t['expected'] else None
        t['unique_recovery'] = t['unique_observed']/t['unique_expected'] if t['unique_expected'] else None
    return details, attribution, list(totals.values()), foreign_count, shared_count
