class StudyModule:
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
