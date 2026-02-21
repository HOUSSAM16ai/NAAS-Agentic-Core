from enum import Enum, auto


class WriterIntent(Enum):
    GENERAL_INQUIRY = auto()
    SOLUTION_REQUEST = auto()
    GRADING_REQUEST = auto()
    DIAGNOSIS_REQUEST = auto()
    QUESTION_ONLY_REQUEST = auto()
