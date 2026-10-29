"""Mount evidence, including reviewed manufacturer specifications.

Reviewed records are model/generation-specific snapshots, not live checks.
Do not extend them to other generations or infer a drivetrain from them.
"""
import re
from html import unescape


CHECKPOINT_SPECS = {
    '5': 'https://www.trekbikes.com/us/en_US/bikes/bikepacking-touring-bikes/checkpoint/checkpoint-sl/f/F224-1/checkpoint-sl-5-axs-gen-3/47071/5321625/',
    '6': 'https://www.trekbikes.com/us/en_US/bikes/bikepacking-touring-bikes/checkpoint/checkpoint-sl/checkpoint-sl-6-axs-gen-3/a/5321655/',
}


def mounting_evidence(item):
    title = ' '.join(unescape(item.get('title', '')).lower().split())
    # Explicitly identify the reviewed model and generation; no family-wide guess.
    model = re.match(r'^(?:trek\s+)?checkpoint\s+sl\s*([56])\s+(axs\s+)?gen\s*3\b', title)
    if (model and (model[1] == '5' or model[2])
            and not re.search(r'\b(?:modified|custom|frameset)\b', title)):
        return 1.0, {'source': CHECKPOINT_SPECS[model[1]],
                     'reviewed_on': '2026-10-29',
                     'basis': 'Manufacturer frame/fork specifications',
                     'details': 'Rack, fender and integrated frame-bag mounts; fork rack mounts'}
    description = re.sub(r'<[^>]+>', ' ', unescape(item.get('description', ''))).lower()
    text = ' '.join((title + ' ' + description).split())
    terms = ['rack mount', 'fork mount', 'cargo mount', 'bikepacking',
             'mounting points', 'fender mount', 'frame bag mount', 'frame-bag mount']
    if any(term in text for term in terms):
        # Negative mount statements need structured interpretation, not credit.
        if re.search(r'\b(?:no|without|not|lack\w*)\b.{0,35}\b(?:mount|rack|fender)', text):
            return None, None
        return 1.0, {'source': item.get('url', ''), 'basis': 'Listing text'}
    return None, None
