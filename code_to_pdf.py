import os
from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'SentinelFlow Source Code (Hackathon Submission)', 0, 1, 'C')

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'Page ' + str(self.page_no()), 0, 0, 'C')

def create_code_pdf():
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    for root, dirs, files in os.walk('.'):
        if any(exclude in root for exclude in ['venv', '.git', '__pycache__', 'models', 'reports', '.pytest_cache']):
            continue
        for file in files:
            if file.endswith('.py') or file.endswith('.html') or file.endswith('.yaml'):
                file_path = os.path.join(root, file)
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 10, f"File: {file_path}", 0, 1)
                pdf.set_font("Courier", size=8)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # FPDF only supports Latin-1 by default
                        content = content.encode('latin-1', 'replace').decode('latin-1')
                        pdf.multi_cell(0, 4, content)
                except Exception as e:
                    pdf.multi_cell(0, 4, f"Error reading file: {e}")
                
                pdf.ln(5)

    pdf.output("SentinelFlow_Source_Code.pdf")

if __name__ == "__main__":
    create_code_pdf()
