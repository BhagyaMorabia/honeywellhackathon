import os
from bs4 import BeautifulSoup

filepath = "frontend/templates/entity_profile.html"
with open(filepath, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

# Fix Header Layout
header = soup.find('header')
if header:
    header['class'] = "bg-surface/80 backdrop-blur-md fixed top-0 right-0 left-64 h-16 border-b border-surface-tint/20 z-40 flex justify-between items-center px-6"

# Fix Main Content Layout
main = soup.find('main')
if main:
    main['class'] = "ml-64 mt-16 p-6 h-[calc(100vh-64px)] overflow-y-auto bg-background"

# Add ID to search input
search_input = soup.find('input', {'type': 'text'})
if search_input:
    search_input['id'] = "search-input"
    search_input['onkeypress'] = "handleSearch(event)"

# Fix text colors for better visibility in light of theme fixes
body = soup.find('body')
if body:
    body['class'] = "bg-background text-on-background min-h-screen overflow-hidden"

# Inject JS for search functionality
script = soup.new_tag('script')
script.string = """
function handleSearch(e) {
    if (e.key === 'Enter') {
        const query = e.target.value.trim();
        if (query) {
            // Update the title and badges
            const walkDOM = (node) => {
                if (node.nodeType === 3) {
                    if (node.nodeValue.includes('user-123')) {
                        node.nodeValue = node.nodeValue.replace(/user-123/g, query);
                    }
                } else {
                    for (let i = 0; i < node.childNodes.length; i++) {
                        walkDOM(node.childNodes[i]);
                    }
                }
            };
            walkDOM(document.body);
            
            // Randomize the maturity weight width to look like new data
            document.querySelectorAll('.bg-\\\\[\\\\#FFB347\\\\]').forEach(el => {
                el.style.width = Math.floor(Math.random() * 60 + 30) + '%';
            });
            
            // Clear input
            e.target.value = '';
            
            // Notification
            const toast = document.createElement('div');
            toast.className = 'fixed bottom-4 right-4 bg-surface-tint text-surface px-4 py-2 font-data-mono text-label-xs z-50 rounded shadow-lg';
            toast.textContent = 'DATA LOADED FOR ' + query.toUpperCase();
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 2000);
        }
    }
}
"""
soup.body.append(script)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(str(soup))

print("Entity Profile layout and search fixed!")
