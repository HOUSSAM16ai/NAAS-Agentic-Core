"""
Domain Constants.
Shared constants and enumerations for the core application domain.
"""

BRANCH_MAP: dict[str, list[str]] = {
    "experimental_sciences": [
        "experimental_sciences",
        "experimental sciences",
        "experimental",
        "علوم تجريبية",
        "تجريبية",
        "علوم تجريبة",
        "science",
        "ex",
        "scien",
        "exp",
    ],
    "math_tech": [
        "math_tech",
        "math tech",
        "technical math",
        "تقني رياضي",
        "تقني",
        "math technique",
        "tm",
        "mt",
    ],
    "mathematics": [
        "mathematics",
        "mathematics_branch",
        "math branch",
        "رياضيات",
        "math",
        "m",
        "رياضي",
    ],
    "foreign_languages": [
        "foreign_languages",
        "languages",
        "لغات أجنبية",
        "لغات",
        "lang",
        "fl",
    ],
    "literature_philosophy": [
        "literature_philosophy",
        "literature",
        "آداب وفلسفة",
        "اداب وفلسفة",
        "اداب",
        "فلسفة",
        "lit",
        "philo",
        "lp",
    ],
}

SUBJECT_MAP: dict[str, list[str]] = {
    "mathematics": [
        "mathematics",
        "math",
        "maths",
        "رياضيات",
        "الرياضيات",
        "جبر",
        "هندسة",
        "calculus",
        "algebra",
        "geometry",
    ],
    "physics": [
        "physics",
        "physic",
        "phy",
        "فيزياء",
        "الفيزياء",
    ],
    "science": [
        "science",
        "sciences",
        "sci",
        "علوم",
        "العلوم",
        "علوم طبيعية",
    ],
}

SET_MAP: dict[str, list[str]] = {
    "subject_1": [
        "subject 1",
        "subject1",
        "s1",
        "sub1",
        "subject_1",
        "الموضوع الأول",
        "الموضوع الاول",
        "الموضوع 1",
        "subject-1",
        "first subject",
    ],
    "subject_2": [
        "subject 2",
        "subject2",
        "s2",
        "sub2",
        "subject_2",
        "الموضوع الثاني",
        "الموضوع الثانى",
        "الموضوع 2",
        "subject-2",
        "second subject",
    ],
}
