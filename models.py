"""
models.py — Data Models for the Exam Hall Allocation System.

Defines the core data structures: Student, ExamHall, Constraint,
AllocationResult, and ConflictReport.  These are pure data containers
with no GUI or file-I/O dependencies.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# ---------------------------------------------------------------------------
#  Enumerations
# ---------------------------------------------------------------------------

class Gender(Enum):
    MALE = "M"
    FEMALE = "F"
    ANY = "Any"


class FloorLevel(Enum):
    GROUND = "Ground"
    UPPER = "Upper"


class AllocationStatus(Enum):
    ALLOCATED = "Allocated"
    CONFLICT = "Conflict"


# ---------------------------------------------------------------------------
#  Student
# ---------------------------------------------------------------------------

@dataclass
class Student:
    roll: int
    department: str
    gender: Gender
    disabled: bool

    @staticmethod
    def from_csv_row(row: dict) -> "Student":
        """Parse a single CSV dict-row into a Student."""
        return Student(
            roll=int(str(row["Roll"]).strip()),
            department=str(row["Dept"]).strip(),
            gender=Gender(str(row["Gender"]).strip()),
            disabled=str(row["Disabled"]).strip().lower() in ("yes", "y", "true", "1"),
        )

    def __repr__(self) -> str:
        return (f"Student(roll={self.roll}, dept={self.department}, "
                f"gender={self.gender.value}, disabled={self.disabled})")


# ---------------------------------------------------------------------------
#  Exam Hall
# ---------------------------------------------------------------------------

@dataclass
class ExamHall:
    name: str
    capacity: int
    gender_allowed: Gender
    dept_mix_allowed: bool
    floor: FloorLevel

    # Runtime state (not from CSV) — tracks current allocation
    assigned_students: List[int] = field(default_factory=list)
    departments_present: set = field(default_factory=set)

    @staticmethod
    def from_csv_row(row: dict) -> "ExamHall":
        """Parse a single CSV dict-row into an ExamHall."""
        return ExamHall(
            name=str(row["Hall"]).strip(),
            capacity=int(str(row["Capacity"]).strip()),
            gender_allowed=Gender(str(row["GenderAllowed"]).strip()),
            dept_mix_allowed=str(row["DeptMix"]).strip().lower() in ("yes", "y", "true", "1"),
            floor=FloorLevel(str(row["Floor"]).strip()),
        )

    @property
    def remaining_capacity(self) -> int:
        return self.capacity - len(self.assigned_students)

    def reset(self):
        """Clear runtime allocation state."""
        self.assigned_students.clear()
        self.departments_present.clear()

    def __repr__(self) -> str:
        return (f"ExamHall({self.name}, cap={self.capacity}, "
                f"gender={self.gender_allowed.value}, "
                f"deptMix={self.dept_mix_allowed}, floor={self.floor.value})")


# ---------------------------------------------------------------------------
#  Constraint Violation Record
# ---------------------------------------------------------------------------

@dataclass
class ConstraintViolation:
    """Records one specific constraint failure for one student–hall pair."""
    hall_name: str
    rule_name: str
    description: str


# ---------------------------------------------------------------------------
#  Allocation Result (per student)
# ---------------------------------------------------------------------------

@dataclass
class AllocationResult:
    student: Student
    status: AllocationStatus
    assigned_hall: Optional[str] = None
    seat_number: Optional[int] = None
    violations: List[ConstraintViolation] = field(default_factory=list)
    explanation: str = ""
    suggestions: List[str] = field(default_factory=list)
