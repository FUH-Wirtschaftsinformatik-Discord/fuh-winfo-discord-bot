#https://rgb.to/rgb/255,255,0
#https://pillow.readthedocs.io/en/stable/reference/ImageFont.html
import re
import requests
from bs4 import BeautifulSoup
from study_module import StudyModule 

# URL of the webpage
url = "https://www.fernuni-hagen.de/wirtschaftswissenschaft/studium/klausurstatistik.shtml"

# Get user input
# search_text = input("Enter the module number: ").strip()

# Send GET request
response = requests.get(url)
response.encoding = "utf-8"  # Ensure correct encoding

# Parse HTML with BeautifulSoup
soup = BeautifulSoup(response.text, "html.parser")

# Find all semester headers (these are usually in <h2>, <h3>, or <div>)
all_elements = soup.find_all(["h2", "h3", "table"])  # Keep structure order

found = False

semester_nr = 0
examination_period = "Unknown"
is_summer_semester = False

# Iterate through elements in order
for element in all_elements:
    if element.name in ["h2", "h3"]:  # If it's a semester header
        current_semester = element.get_text(strip=True)
        
        for semester_part in current_semester.lower().split(" "):
            if semester_part.isdigit():
                semester_nr = int(semester_part)
            elif "sommer" in semester_part:
                is_summer_semester = True
            elif semester_part.startswith("p"):
                examination_period = semester_part.upper()
        
    elif element.name == "table":  # If it's a table
        rows = element.find_all("tr")
        # table_contains_module = False
        
        if len(rows) != 3:
            print(f"Something is off with the table for {current_semester}, it has {len(rows)} rows.")
            continue

        row_1 = [col.get_text(strip=True) for col in rows[0].find_all(["th", "td"])]
        row_3 = [col.get_text(strip=True) for col in rows[2].find_all(["th", "td"])]

        module_number: str = row_1[0].strip()
        module_name: str = row_1[1].strip()


        new_module = StudyModule(
            module_number=module_number,
            module_name=module_name,
            is_summer_semester=is_summer_semester,
            year=semester_nr,
            examination_period=examination_period
        )        

        # <tr> <td>Teilnehmer</td> <td>sehr gut</td> <td>gut</td> <td>befriedigend</td> <td>ausreichend</td> <td>nicht ausreichend</td> </tr>

        module_participants = 0
        module_very_good = 0
        module_good = 0
        module_satisfactory = 0
        module_sufficient = 0
        module_insufficient_grade = 0

        if row_3[0].strip().isnumeric():
            module_participants = int(row_3[0].strip())
        if row_3[1].strip().isnumeric():
            module_very_good = int(row_3[1].strip())
        if row_3[2].strip().isnumeric():
            module_good = int(row_3[2].strip())
        if row_3[3].strip().isnumeric():
            module_satisfactory = int(row_3[3].strip())
        if row_3[4].strip().isnumeric():
            module_sufficient = int(row_3[4].strip())
        if row_3[5].strip().isnumeric():
            module_insufficient_grade = int(row_3[5].strip())

        if module_satisfactory > 0:

            print(f"\n📌 **Table for Semester: {current_semester}**\n")
            print(f"Module Semester: {new_module.year} {'Summer' if new_module.is_summer_semester else 'Winter'}")
            print(f"Module Number: {module_number}")
            print(f"Module Name: {module_name}")
            print(f"Very Good (1.0 - 1.5): {module_very_good}")
            print(f"Good (1.6 - 2.5): {module_good}")
            print(f"Satisfactory (2.6 - 3.5): {module_satisfactory}")
            print(f"Sufficient (3.6 - 4.0): {module_sufficient}")
            print(f"Insufficient Grade (5.0): {module_insufficient_grade}")
