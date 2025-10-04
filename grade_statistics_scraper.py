import asyncio
import httpx
from bs4 import BeautifulSoup, ResultSet
from dotenv import load_dotenv
from models import ModuleGradeStatistics
from grade_statistics import GradeStatistics


class GradeStatisticsScraper:
    # URL to scrape grade statistics from
    URL = "https://www.fernuni-hagen.de/wirtschaftswissenschaft/studium/klausurstatistik.shtml"

    async def download_page(self) -> ResultSet:
        """
        Download the statistics page and return all relevant HTML elements.
        Returns a list of h2, h3, and table elements.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(self.URL)
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")
            return soup.find_all(["h2", "h3", "table"])

    async def extract_modules(self, page_content: ResultSet) -> list[GradeStatistics]:
        """
        Parse the HTML content and extract all module statistics.
        Returns a list of GradeStatistics objects.
        """
        extracted_modules: list[GradeStatistics] = []
        year = 0
        examination_period = "Unknown"
        is_summer_semester = False
        # Iterate over all elements (headers and tables)
        for element in page_content:
            if element.name in ["h2", "h3"]:
                # Parse semester header to get year, semester type, and period
                current_semester: str = element.get_text(strip=True)
                for semester_part in current_semester.lower().split(" "):
                    has_slash = semester_part.count("/") > 0
                    if has_slash:
                        years = semester_part.split("/")
                        if len(years) == 2 and years[0].isdigit() and years[1].isdigit():
                            year = int(years[0])
                            year += 1
                            is_summer_semester = False
                    elif semester_part.isdigit():
                        year = int(semester_part)
                    elif "sommer" in semester_part:
                        is_summer_semester = True
                    elif "winter" in semester_part:
                        is_summer_semester = False
                    elif semester_part.startswith("p"):
                        examination_period = semester_part.upper()
            elif element.name == "table":
                # Parse table rows for module statistics
                rows = element.find_all("tr")
                if len(rows) != 3:
                    print(f"Something is off with the table for {current_semester}, it has {len(rows)} rows.")
                    continue
                row_1 = [col.get_text(strip=True) for col in rows[0].find_all(["th", "td"])]
                row_3 = [col.get_text(strip=True) for col in rows[2].find_all(["th", "td"])]
                module_number: str = row_1[0].strip()
                module_name: str = row_1[1].strip()
                new_module = GradeStatistics(
                    module_number=module_number,
                    module_name=module_name,
                    is_summer_semester=is_summer_semester,
                    year=year,
                    examination_period=examination_period
                )
                # Parse grades and participants
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
                    print(f"Error parsing numbers for module {module_number} - {module_name} in semester {year} ({'SS' if is_summer_semester else 'WS'}) - {examination_period}. Skipping this module.")
                    new_module.anonyomous = True
                # Assign grades to module
                new_module.very_good = module_very_good
                new_module.good = module_good
                new_module.satisfactory = module_satisfactory
                new_module.sufficient = module_sufficient
                new_module.insufficient = module_insufficient_grade
                # Skip modules with zero participants
                if new_module.get_participant_count() == 0:
                    print(f"Skipping: Module {module_number} - {module_name} for semester {year} ({'SS' if is_summer_semester else 'WS'}) - {examination_period} has zero participants.")
                    continue
                extracted_modules.append(new_module)
                print(f"Added module: {module_number} - {module_name} for semester {year} ({'SS' if is_summer_semester else 'WS'}) - {examination_period} with {module_participants} participants.")
                print(f"Grades: Very Good: {module_very_good}, Good: {module_good}, Satisfactory: {module_satisfactory}, Sufficient: {module_sufficient}, Insufficient: {module_insufficient_grade}")
        return extracted_modules

    async def get_changes(self, modules: list[GradeStatistics]) -> dict:
        """
        Compare extracted modules with database entries and determine which modules are new or have changed grades.
        Returns a dictionary with lists of added and changed modules.
        """
        change_container = {
            "added_modules": [],
            "changed_modules": []
        }
        for changed_module in modules:
            existing_study_module: ModuleGradeStatistics = None
            # Check if module already exists in the database
            try:
                existing_study_module = ModuleGradeStatistics.get_or_none(
                    module_number=changed_module.module_number,
                    is_summer_semester=changed_module.is_summer_semester,
                    examination_period=changed_module.examination_period,
                    year=changed_module.year
                )
            except Exception:
                existing_study_module = None
            # If it doesn't exist, add to added_modules
            if not existing_study_module:
                change_container["added_modules"].append({
                    "module_number": int(changed_module.module_number),
                    "module_name": changed_module.module_name,
                    "is_summer_semester": changed_module.is_summer_semester,
                    "year": changed_module.year,
                    "examination_period": changed_module.examination_period,
                    "anonymous": getattr(changed_module, "anonyomous", False),
                    "very_good": changed_module.very_good,
                    "good": changed_module.good,
                    "satisfactory": changed_module.satisfactory,
                    "sufficient": changed_module.sufficient,
                    "insufficient": changed_module.insufficient
                })
                continue
            # If it exists, check if any grades have changed
            has_module_changed = (
                existing_study_module.very_good != changed_module.very_good or
                existing_study_module.good != changed_module.good or
                existing_study_module.satisfactory != changed_module.satisfactory or
                existing_study_module.sufficient != changed_module.sufficient or
                existing_study_module.insufficient != changed_module.insufficient
            )
            if has_module_changed:
                change_container["changed_modules"].append({
                    "existing": existing_study_module,
                    "new_grades": {
                        "very_good": changed_module.very_good,
                        "good": changed_module.good,
                        "satisfactory": changed_module.satisfactory,
                        "sufficient": changed_module.sufficient,
                        "insufficient": changed_module.insufficient
                    }
                })
        return change_container

    async def store_added(self, list_of_modules: list[ModuleGradeStatistics]) -> None:
        """
        Add new modules to the database.
        Each module in the list is inserted as a new record.
        """
        for module in list_of_modules:
            try:
                with ModuleGradeStatistics._meta.database.atomic() as txn:
                    ModuleGradeStatistics.create(
                        module_number=int(module["module_number"]),
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

    async def store_updated(self, list_of_modules: list[ModuleGradeStatistics]):
        """
        Update existing modules in the database with new grade values.
        Each module in the list is updated if grades have changed.
        """
        for module_change in list_of_modules:
            existing: ModuleGradeStatistics = module_change["existing"]
            new_grades = module_change["new_grades"]
            try:
                with ModuleGradeStatistics._meta.database.atomic() as txn:
                    existing_study_module = ModuleGradeStatistics.get_or_none(
                        module_number=existing.module_number,
                        is_summer_semester=existing.is_summer_semester,
                        examination_period=existing.examination_period,
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
        """
        Main entry point for scraping and syncing grade statistics.
        Downloads, parses, and updates the database as needed.
        """
        print("Starting WiWi Scraper...")
        print("Downloading page...")
        page_content = await self.download_page()
        print("Extracting modules...")
        modules = await self.extract_modules(page_content)
        print(f"Total modules found: {len(modules)}")
        change_container = await self.get_changes(modules)
        print(f"Modules to add: {len(change_container['added_modules'])}")
        print(f"Modules to update: {len(change_container['changed_modules'])}")
        print("Storing changes to database...")
        await self.store_added(change_container["added_modules"])
        print("Added new modules.")
        await self.store_updated(change_container["changed_modules"])
        print("Updated existing modules.")
        print("Done.")

if __name__ == "__main__":
    load_dotenv()
    scraper = GradeStatisticsScraper()
    asyncio.run(scraper.run())