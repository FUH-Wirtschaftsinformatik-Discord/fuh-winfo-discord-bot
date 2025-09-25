import httpx
from bs4 import BeautifulSoup, ResultSet
from wiwi_models import StudyModuleModel
from study_module import StudyModule

class WiwiScraper:
    URL = "https://www.fernuni-hagen.de/wirtschaftswissenschaft/studium/klausurstatistik.shtml"

    def __init__(self, ):
        self.session = httpx.AsyncClient()

    async def download_page(self) -> ResultSet:
        async with httpx.AsyncClient() as client:
            response = await client.get(self.URL)
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")
            all_elements = soup.find_all(["h2", "h3", "table"])
            return all_elements

    async def extract_modules(self, page_content: ResultSet) -> list[StudyModule]:
        modules: list[StudyModule] = []
        semester_nr = 0
        examination_period = "Unknown"
        is_summer_semester = False

        for element in page_content:
            if element.name in ["h2", "h3"]:
                current_semester: str = element.get_text(strip=True)
                for semester_part in current_semester.lower().split(" "):

                    has_slash = semester_part.count("/") > 0
                    if has_slash:
                        years = semester_part.split("/")
                        if len(years) == 2 and years[0].isdigit() and years[1].isdigit():
                            semester_nr = int(years[0])
                            semester_nr += 1
                            is_summer_semester = False
                    elif semester_part.isdigit():
                        semester_nr = int(semester_part)
                    elif "sommer" in semester_part:
                        is_summer_semester = True
                    elif "winter" in semester_part:
                        is_summer_semester = False
                    elif semester_part.startswith("p"):
                        examination_period = semester_part.upper()
            elif element.name == "table":
                rows = element.find_all("tr")
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
                except Exception:
                    print(f"Error parsing numbers for module {module_number} - {module_name} in semester {semester_nr} ({'SS' if is_summer_semester else 'WS'}) - {examination_period}. Skipping this module.")
                    new_module.anonyomous = True
                new_module.add_grade("very_good", module_very_good)
                new_module.add_grade("good", module_good)
                new_module.add_grade("satisfactory", module_satisfactory)
                new_module.add_grade("sufficient", module_sufficient)
                new_module.add_grade("insufficient", module_insufficient_grade)
                modules.append(new_module)
                print(f"Added module: {module_number} - {module_name} for semester {semester_nr} ({'SS' if is_summer_semester else 'WS'}) - {examination_period} with {module_participants} participants.")
                print(f"Grades: Very Good: {module_very_good}, Good: {module_good}, Satisfactory: {module_satisfactory}, Sufficient: {module_sufficient}, Insufficient: {module_insufficient_grade}")
        
        return modules

    async def get_changes(self, modules):
        change_container = {
            "added_modules": [],
            "changed_modules": []
        }
        for module in modules:
            existing_study_module: StudyModuleModel = None
            try:
                existing_study_module = StudyModuleModel.get_or_none(
                    module_number=module.module_number ,
                    is_summer_semester=module.is_summer_semester ,
                    examination_period=module.examination_period ,
                    year=module.year
                )

            except Exception:
                existing_study_module = None
                pass


            new_very_good = module.get_grade("very_good")
            new_good = module.get_grade("good")
            new_satisfactory = module.get_grade("satisfactory")
            new_sufficient = module.get_grade("sufficient") 
            new_insufficient = module.get_grade("insufficient")
            if not existing_study_module:
                change_container["added_modules"].append({
                    "module_number": module.module_number,
                    "module_name": module.module_name,
                    "is_summer_semester": module.is_summer_semester,
                    "year": module.year,
                    "examination_period": module.examination_period,
                    "anonymous": getattr(module, "anonyomous", False),
                    "very_good": new_very_good,
                    "good": new_good,
                    "satisfactory": new_satisfactory,
                    "sufficient": new_sufficient,
                    "insufficient": new_insufficient
                })
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
                change_container["changed_modules"].append({
                    "existing": existing_study_module,
                    "new_grades": {
                        "very_good": new_very_good,
                        "good": new_good,
                        "satisfactory": new_satisfactory,
                        "sufficient": new_sufficient,
                        "insufficient": new_insufficient
                    }
                })
        return change_container

    async def store_added(self, list_of_modules: list[StudyModuleModel]) -> None:
        # add to database
        for module in list_of_modules:
            try:
                with StudyModuleModel._meta.database.atomic() as txn:
                    StudyModuleModel.create(
                        module_number=module["module_number"],
                        module_name=module["module_name"],
                        is_summer_semester=module["is_summer_semester"],
                        year=module["year"],
                        examination_period=module["examination_period"],
                        anonymous=module.get("anonymous", False),
                        very_good=module["very_good"],
                        good=module["good"],
                        satisfactory=module["satisfactory"],
                        sufficient=module["sufficient"],
                        insufficient=module["insufficient"]
                    )
                    txn.commit()
            except Exception as e:
                print(f"Error adding module {module['module_number']} - {module['module_name']}: {e}")

    async def store_updated(self, list_of_modules: list[StudyModuleModel]):
        # update in database
        for module_change in list_of_modules:
            existing: StudyModuleModel = module_change["existing"]
            new_grades = module_change["new_grades"]
            try:
                with StudyModuleModel._meta.database.atomic() as txn:                   
                    existing_study_module = StudyModuleModel.get_or_none(
                            module_number=existing.module_number,
                            is_summer_semester=existing.is_summer_semester ,
                            examination_period=existing.examination_period ,
                            year=existing.year
                        )                
                    existing_study_module.very_good = new_grades["very_good"]
                    existing_study_module.good = new_grades["good"]
                    existing_study_module.satisfactory = new_grades["satisfactory"]
                    existing_study_module.sufficient = new_grades["sufficient"]
                    existing_study_module.insufficient = new_grades["insufficient"]

                    existing_study_module.save()    
                    
                    txn.commit()
            except Exception as e:
                print(f"Error updating module {existing.module_number} - {existing.module_name}: {e}")

    async def run(self):
        print("Starting WiWi Scraper...")

        print("Downloading page...")
        page_content = await self.download_page()
        
        print("Extracting modules...")
        modules = await self.extract_modules(page_content)
        print(f"\nTotal modules found: {len(modules)}")

        change_container = await self.get_changes(modules)
        print(f"Modules to add: {len(change_container['added_modules'])}")
        print(f"Modules to update: {len(change_container['changed_modules'])}")
        
        print("Storing changes to database...")
        await self.store_added(change_container["added_modules"])
        print("Added new modules.")
        await self.store_updated(change_container["changed_modules"])
        print("Updated existing modules.")

        print("Done.")

