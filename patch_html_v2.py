import os
from bs4 import BeautifulSoup

def patch_file(filename):
    filepath = os.path.join("frontend", "templates", filename)
    if not os.path.exists(filepath):
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    # 1. Update Navigation Links (Sidebar)
    for a in soup.find_all('a'):
        text = a.text.strip().upper()
        if 'COMMAND CENTER' in text:
            a['href'] = '/'
            a['onclick'] = ""
        elif 'TRIAGE QUEUE' in text:
            a['href'] = '/triage'
            a['onclick'] = ""
        elif 'INVESTIGATION' in text:
            a['href'] = '/investigation'
            a['onclick'] = ""
        elif 'ENTITY PROFILE' in text:
            a['href'] = '/entity_profile'
            a['onclick'] = ""
        elif 'SYSTEM STATUS' in text or 'SETTINGS' in text or 'MODELS' in text or 'IFOREST' in text or 'MARKOV' in text:
            a['href'] = '#'
            a['onclick'] = "alert('This feature is currently locked in the MVP demo.'); return false;"

    # 2. Update Buttons
    for btn in soup.find_all('button'):
        text = btn.text.strip().upper()
        if 'INITIATE_SCAN' in text:
            btn['onclick'] = "alert('Deep Scan initiated across all clusters...');"
        elif 'ELEVATE_PRIVILEGES' in text:
            btn['onclick'] = "alert('Error: Requires biometric authentication.');"
        elif 'QUARANTINE ENTITY' in text:
            btn['onclick'] = "alert('Entity has been successfully quarantined.');"

    # Add the script for layout injection (if it's not already there)
    # The user was stuck on investigation.html, let's make sure it has the links properly mapped.
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(str(soup))

for f in ["index.html", "triage.html", "investigation.html", "entity_profile.html"]:
    patch_file(f)
print("All HTML files patched!")
