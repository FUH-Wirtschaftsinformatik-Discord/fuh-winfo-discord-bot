#https://rgb.to/rgb/255,255,0
#https://pillow.readthedocs.io/en/stable/reference/ImageFont.html
import requests
from bs4 import BeautifulSoup

# URL of the webpage
url = "https://www.fernuni-hagen.de/wirtschaftswissenschaft/studium/klausurstatistik.shtml"

# Get user input
search_text = input("Enter the module number: ").strip()

# Send GET request
response = requests.get(url)
response.encoding = "utf-8"  # Ensure correct encoding

# Parse HTML with BeautifulSoup
soup = BeautifulSoup(response.text, "html.parser")

# Find all semester headers (these are usually in <h2>, <h3>, or <div>)
all_elements = soup.find_all(["h2", "h3", "table"])  # Keep structure order

found = False
current_semester = "Unknown Semester"

# Iterate through elements in order
for element in all_elements:
    if element.name in ["h2", "h3"]:  # If it's a semester header
        current_semester = element.get_text(strip=True)
    elif element.name == "table":  # If it's a table
        rows = element.find_all("tr")
        table_contains_module = False
        
        for row in rows:
            columns = [col.get_text(strip=True) for col in row.find_all(["th", "td"])]
            if any(search_text in col for col in columns):
                table_contains_module = True
                found = True
                break  # Stop checking rows, we found the module
        
        if table_contains_module:
            print(f"\n📌 **Table for Semester: {current_semester}**\n")
            for row in rows:
                print([col.get_text(strip=True) for col in row.find_all(["th", "td"])])

if not found:
    print(f"\n❌ No table found for module {search_text}.")