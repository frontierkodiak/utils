import os
import sys
import requests
from bs4 import BeautifulSoup
import img2pdf
import yaml
from urllib.parse import unquote


# Check if the output directory and links file arguments are provided
if len(sys.argv) < 3:
    print("Usage: python script.py output_dir links_file")
    sys.exit()

output_dir, links_file = sys.argv[1:3]

# Create output directory if it doesn't exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Read and process links from the YAML file
with open(links_file, 'r') as file:
    entries = yaml.safe_load(file)

for entry in entries:
    link = entry['link']
    title = entry['title']
    found_round = entry['funding_round'].replace(" ", "_")

    pdf_filename = os.path.join(output_dir, f"{title}_{found_round}_deck.pdf")

    response = requests.get(link)
    html_content = response.text
    soup = BeautifulSoup(html_content, 'lxml')  
    images = soup.find_all('img')
    image_urls = [unquote(img.get('src')) for img in images if '.png' in unquote(img.get('src'))]

    image_dir = os.path.join(output_dir, "images")
    if not os.path.exists(image_dir):
        os.makedirs(image_dir)

    image_files = []
    for i, img_url in enumerate(image_urls):
        img_data = requests.get(img_url).content
        filename = os.path.join(image_dir, f"image{i}.png")
        with open(filename, 'wb') as handler:
            handler.write(img_data)
        image_files.append(filename)

    with open(pdf_filename, "wb") as f:
        f.write(img2pdf.convert([i for i in image_files if i.endswith(".png")]))

    print(f"PDF created successfully: {pdf_filename}")
