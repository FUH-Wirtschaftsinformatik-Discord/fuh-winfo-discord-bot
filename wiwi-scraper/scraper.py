#https://rgb.to/rgb/255,255,0
#https://pillow.readthedocs.io/en/stable/reference/ImageFont.html
from datetime import time
from wiwi_models import StudyModuleModel 
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

modules: list[StudyModule] = []

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

        module_participants = 0
        module_very_good = 0
        module_good = 0
        module_satisfactory = 0
        module_sufficient = 0
        module_insufficient_grade = 0

        try:
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
        except:
            print(f"Error parsing numbers for module {module_number} - {module_name} in semester {semester_nr} ({'SS' if is_summer_semester else 'WS'}) - {examination_period}. Skipping this module.")
            new_module.anonyomous=True

        new_module.add_grade("very_good", module_very_good)
        new_module.add_grade("good", module_good)
        new_module.add_grade("satisfactory", module_satisfactory)
        new_module.add_grade("sufficient", module_sufficient)
        new_module.add_grade("insufficient", module_insufficient_grade)

        modules.append(new_module)

        print(f"Added module: {module_number} - {module_name} for semester {semester_nr} ({'SS' if is_summer_semester else 'WS'}) - {examination_period} with {module_participants} participants.")
        print(f"Grades: Very Good: {module_very_good}, Good: {module_good}, Satisfactory: {module_satisfactory}, Sufficient: {module_sufficient}, Insufficient: {module_insufficient_grade}")

print(f"\nTotal modules found: {len(modules)}")


for module in modules:    

    # Check if module already exists in DB
    existing_study_module = StudyModuleModel.get(module_number=module.module_number, 
                                                 module_name=module.module_name,
                                                 is_summer_semester=module.is_summer_semester,
                                                 examination_period=module.examination_period,)

    new_very_good = module.get_grade("very_good") or 0
    new_good = module.get_grade("good") or 0
    new_satisfactory = module.get_grade("satisfactory") or 0
    new_sufficient = module.get_grade("sufficient") or 0
    new_insufficient = module.get_grade("insufficient") or 0

    

    if not existing_study_module:

        StudyModuleModel.create(
            module_number=module.module_number,
            module_name=module.module_name,
            is_summer_semester=module.is_summer_semester,
            year=module.year,
            examination_period=module.examination_period,
            anonymous=module.anonyomous,
            very_good=new_very_good,
            good=new_good,
            satisfactory=new_satisfactory,
            sufficient=new_sufficient,
            insufficient=new_insufficient
        )

        continue

    old_very_good = existing_study_module.very_good
    old_good = existing_study_module.good
    old_satisfactory = existing_study_module.satisfactory
    old_sufficient = existing_study_module.sufficient
    old_insufficient = existing_study_module.insufficient

    changed = (
        old_very_good != new_very_good or
        old_good != new_good or
        old_satisfactory != new_satisfactory or
        old_sufficient != new_sufficient or
        old_insufficient != new_insufficient
    )

    if changed:
        print(f"Updating module {module.module_number} - {module.module_name} for semester {module.year} ({'SS' if module.is_summer_semester else 'WS'}) - {module.examination_period}.")
        print(f"Old Grades: Very Good: {old_very_good}, Good: {old_good}, Satisfactory: {old_satisfactory}, Sufficient: {old_sufficient}, Insufficient: {old_insufficient}")
        print(f"New Grades: Very Good: {new_very_good}, Good: {new_good}, Satisfactory: {new_satisfactory}, Sufficient: {new_sufficient}, Insufficient: {new_insufficient}")

        existing_study_module.very_good = new_very_good
        existing_study_module.good = new_good
        existing_study_module.satisfactory = new_satisfactory
        existing_study_module.sufficient = new_sufficient
        existing_study_module.insufficient = new_insufficient


        with StudyModuleModel._meta.database.atomic():  # transaction context
            StudyModuleModel.save(existing_study_module)

            pass


    else:
        print(f"No changes for module {module.module_number} - {module.module_name} for semester {module.year} ({'SS' if module.is_summer_semester else 'WS'}) - {module.examination_period}. Skipping update.")
