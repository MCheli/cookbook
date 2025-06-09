import os
import markdown
from weasyprint import HTML

def md_to_html_with_pagebreaks(md_content):
    # Insert page breaks before each H2 header
    md_content_with_breaks = md_content.replace('\n## ', '\n<div style="page-break-before: always;"></div>\n## ')
    html_body = markdown.markdown(md_content_with_breaks, extensions=['extra', 'toc'])
    full_html = f"""
    <html>
    <head>
        <style>
            @page {{ margin: 1in; }}
            body {{ font-family: Arial, sans-serif; }}
            div[style*="page-break-before"] {{ display: block; height: 0; }}
            h1, h2, h3, h4, h5, h6 {{ page-break-after: avoid; }}
        </style>
    </head>
    <body>
        {html_body}
    </body>
    </html>
    """
    return full_html

def convert_md_file_to_pdf(md_path, output_pdf_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    html_content = md_to_html_with_pagebreaks(md_content)
    HTML(string=html_content).write_pdf(output_pdf_path)

def batch_convert_md_in_folder(folder_path, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    for filename in os.listdir(folder_path):
        if filename.endswith('.md'):
            md_path = os.path.join(folder_path, filename)
            pdf_filename = os.path.splitext(filename)[0] + '.pdf'
            output_pdf_path = os.path.join(output_folder, pdf_filename)
            print(f'Converting {filename} → {pdf_filename}')
            convert_md_file_to_pdf(md_path, output_pdf_path)
    print('✅ All Markdown files converted!')

# Example usage:
input_folder = './'
output_folder = './pdf'

batch_convert_md_in_folder(input_folder, output_folder)