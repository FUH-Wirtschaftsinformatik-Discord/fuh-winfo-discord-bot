class GradeStatistics:
    def __init__(self, module_number: str, 
                 module_name: str,
                 is_summer_semester: bool,
                 year: int,
                 examination_period: str) -> None:
        self.module_number = module_number
        self.module_name = module_name
        self.is_summer_semester = is_summer_semester
        self.year = year
        self.examination_period = examination_period
        self.grades_overview = {}  # key: student_id or exam_id, value: grade
        self.anonyomous=False

    def add_grade(self, key: str, grade: int) -> None:
        """Add or update a grade for a given key (e.g., student or exam attempt)."""
        self.grades_overview[key] = grade

    def get_grade(self, key: str) -> int:
        """Retrieve the grade for a given key."""
        return self.grades_overview.get(key)

    def get_all_grades(self) -> dict:
        """Return the entire overview of grades."""
        return self.grades_overview