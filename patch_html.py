import os
from bs4 import BeautifulSoup

def patch_index():
    filepath = "frontend/templates/index.html"
    with open(filepath, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    # 1. Update Navigation Links
    for a in soup.find_all('a'):
        text = a.text.strip().upper()
        if 'COMMAND CENTER' in text:
            a['href'] = '/'
        elif 'TRIAGE QUEUE' in text:
            a['href'] = '/triage'
        elif 'INVESTIGATION' in text:
            a['href'] = '/investigation'

    # 2. Add IDs for data injection
    # Live Events/Sec
    divs = soup.find_all('div', class_='font-headline-lg')
    if len(divs) >= 1: divs[0]['id'] = 'live-events'
    if len(divs) >= 2: divs[1]['id'] = 'ingestion-delay'

    # System KPIs
    kpi_divs = soup.find_all('div', class_='text-surface-tint')
    # Find the ones that have large text (like 1.2M, 14, 0.04)
    for div in kpi_divs:
        if '1.2M' in div.text:
            div['id'] = 'events-analyzed'
        elif '14' in div.text:
            div['id'] = 'active-critical'
        elif '0.04' in div.text:
            div['id'] = 'drift-index'

    # Live Event Stream container
    # The parent of the log entries
    log_entries = soup.find_all('div', class_='log-entry')
    if log_entries:
        container = log_entries[0].parent
        container['id'] = 'event-stream-container'
        container.clear() # clear mock data

    # 3. Inject Script
    script = soup.new_tag('script')
    script.string = """
        async function updateDashboard() {
            try {
                const response = await fetch('/api/v1/metrics');
                const data = await response.json();
                
                const el1 = document.getElementById('events-analyzed');
                if (el1) el1.textContent = (data.events_analyzed_24h / 1000000).toFixed(1) + 'M';
                
                const el2 = document.getElementById('active-critical');
                if (el2) el2.textContent = data.active_critical_alerts;
                
                const el3 = document.getElementById('drift-index');
                if (el3) el3.textContent = data.concept_drift_global_index.toFixed(2);
                
                const el4 = document.getElementById('live-events');
                if (el4) el4.textContent = data.live_events_per_sec.toLocaleString();
                
                const el5 = document.getElementById('ingestion-delay');
                if (el5) el5.textContent = data.ingestion_delay_ms + 'ms';
                
                const streamContainer = document.getElementById('event-stream-container');
                if (streamContainer && data.recent_events) {
                    streamContainer.innerHTML = '';
                    data.recent_events.forEach(event => {
                        const el = document.createElement('div');
                        el.className = 'font-data-mono text-[10px] bg-surface-container-high p-2 border-l-2 border-surface-tint rounded log-entry mb-2';
                        const timeStr = event.timestamp.substring(11, 23);
                        el.innerHTML = `
                            <div class="flex justify-between text-on-surface-variant mb-1">
                                <span>[${timeStr}]</span>
                                <span class="${event.risk > 80 ? 'text-error' : 'text-surface-tint'}">RISK_${event.risk}</span>
                            </div>
                            <div class="text-on-surface whitespace-pre-wrap break-all">{ "event_id": "${event.event_id}", "entity_id": "${event.entity_id}", "risk": ${event.risk}, "type": "${event.type}" }</div>
                        `;
                        streamContainer.appendChild(el);
                    });
                }
            } catch (e) {
                console.error('Failed to fetch metrics', e);
            }
        }
        updateDashboard();
        setInterval(updateDashboard, 2000);
    """
    soup.body.append(script)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(str(soup))

def patch_triage():
    filepath = "frontend/templates/triage.html"
    if not os.path.exists(filepath): return
    with open(filepath, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    # 1. Update Navigation Links
    for a in soup.find_all('a'):
        text = a.text.strip().upper()
        if 'COMMAND CENTER' in text:
            a['href'] = '/'
        elif 'TRIAGE QUEUE' in text:
            a['href'] = '/triage'
        elif 'INVESTIGATION' in text:
            a['href'] = '/investigation'
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(str(soup))

patch_index()
patch_triage()
print("HTML Patched!")
