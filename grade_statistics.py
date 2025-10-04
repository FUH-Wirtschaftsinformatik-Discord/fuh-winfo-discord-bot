class GradeStatistics:
    def __init__(self, 
                 module_number: str, 
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
        self.very_good=0
        self.good=0
        self.satisfactory=0
        self.sufficient=0
        self.insufficient=0
    
    def get_participant_count(self) -> int:
        participants = self.very_good + self.good + self.satisfactory + self.sufficient + self.insufficient
        return participants