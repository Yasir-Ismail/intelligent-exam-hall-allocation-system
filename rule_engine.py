"""
rule_engine.py — Declarative Rule Engine for Exam Hall Allocation.

Each rule is an independent callable that receives a Student and an ExamHall
(with its current runtime state) and returns either None (pass) or a
ConstraintViolation (fail).

Rules are *completely separated* from GUI and solver logic.  New rules can
be added simply by writing a function and registering it.
"""

from typing import Callable, Dict, List, Optional, Tuple

from models import (
    ConstraintViolation,
    ExamHall,
    FloorLevel,
    Gender,
    Student,
)

# Type alias for a rule function.
# Returns None when the constraint is satisfied, or a ConstraintViolation.
RuleFunction = Callable[[Student, ExamHall], Optional[ConstraintViolation]]


# ═══════════════════════════════════════════════════════════════════════════
#  Individual Rule Definitions
# ═══════════════════════════════════════════════════════════════════════════

def rule_capacity(student: Student, hall: ExamHall) -> Optional[ConstraintViolation]:
    """R1: A hall cannot exceed its seating capacity."""
    if hall.remaining_capacity <= 0:
        return ConstraintViolation(
            hall_name=hall.name,
            rule_name="Capacity Constraint",
            description=(
                f"Hall {hall.name} is full ({hall.capacity}/{hall.capacity} seats occupied). "
                f"No room for Student {student.roll}."
            ),
        )
    return None


def rule_gender(student: Student, hall: ExamHall) -> Optional[ConstraintViolation]:
    """R2: A student's gender must match the hall's allowed-gender policy."""
    if hall.gender_allowed == Gender.ANY:
        return None
    if student.gender != hall.gender_allowed:
        return ConstraintViolation(
            hall_name=hall.name,
            rule_name="Gender Constraint",
            description=(
                f"Hall {hall.name} allows only '{hall.gender_allowed.value}' students, "
                f"but Student {student.roll} is '{student.gender.value}'."
            ),
        )
    return None


def rule_department_mixing(student: Student, hall: ExamHall) -> Optional[ConstraintViolation]:
    """R3: If department mixing is disallowed, only one department per hall."""
    if hall.dept_mix_allowed:
        return None
    if hall.departments_present and student.department not in hall.departments_present:
        existing = ", ".join(sorted(hall.departments_present))
        return ConstraintViolation(
            hall_name=hall.name,
            rule_name="Department Mixing Constraint",
            description=(
                f"Hall {hall.name} does not allow department mixing. "
                f"Department(s) already present: [{existing}]. "
                f"Student {student.roll} belongs to '{student.department}'."
            ),
        )
    return None


def rule_disabled_ground_floor(student: Student, hall: ExamHall) -> Optional[ConstraintViolation]:
    """R4: Disabled students must be assigned to ground-floor halls."""
    if not student.disabled:
        return None
    if hall.floor != FloorLevel.GROUND:
        return ConstraintViolation(
            hall_name=hall.name,
            rule_name="Disabled Accessibility Constraint",
            description=(
                f"Student {student.roll} is disabled and requires a ground-floor hall, "
                f"but Hall {hall.name} is on floor '{hall.floor.value}'."
            ),
        )
    return None


def rule_anti_cheating_adjacent(student: Student, hall: ExamHall) -> Optional[ConstraintViolation]:
    """R5: No two students with consecutive roll numbers in the same hall
    should receive adjacent seat numbers.

    Implementation: We check if placing the student *would* create an
    adjacency conflict.  With a simple sequential seat assignment (seat =
    number of students already seated + 1), the previous seat's occupant is
    the last student added.  If that student's roll number is consecutive
    with the new student's, the constraint fires.
    """
    if not hall.assigned_students:
        return None

    # The last student seated gets the seat immediately before this one.
    last_roll = hall.assigned_students[-1]
    if abs(student.roll - last_roll) == 1:
        return ConstraintViolation(
            hall_name=hall.name,
            rule_name="Anti-Cheating (Adjacent Roll) Constraint",
            description=(
                f"Seating Student {student.roll} next to Student {last_roll} "
                f"in Hall {hall.name} violates the anti-cheating rule "
                f"(consecutive roll numbers on adjacent seats)."
            ),
        )
    return None


# ═══════════════════════════════════════════════════════════════════════════
#  Rule Registry
# ═══════════════════════════════════════════════════════════════════════════

class RuleEngine:
    """
    Manages an ordered collection of constraint rules and evaluates them
    against student–hall pairs.
    """

    def __init__(self):
        # List of (rule_id, display_name, function, enabled)
        self._rules: List[Tuple[str, str, RuleFunction, bool]] = []
        self._register_defaults()

    # ----- registration helpers -----------------------------------------

    def _register_defaults(self):
        """Register the five built-in rules."""
        self.register("R1", "Capacity Constraint", rule_capacity)
        self.register("R2", "Gender Constraint", rule_gender)
        self.register("R3", "Dept Mixing Constraint", rule_department_mixing)
        self.register("R4", "Disabled Accessibility", rule_disabled_ground_floor)
        self.register("R5", "Anti-Cheating Adjacent", rule_anti_cheating_adjacent)

    def register(self, rule_id: str, display_name: str,
                 func: RuleFunction, enabled: bool = True):
        self._rules.append((rule_id, display_name, func, enabled))

    # ----- enable / disable ---------------------------------------------

    def set_enabled(self, rule_id: str, enabled: bool):
        self._rules = [
            (rid, name, fn, enabled if rid == rule_id else en)
            for rid, name, fn, en in self._rules
        ]

    def is_enabled(self, rule_id: str) -> bool:
        for rid, _, _, en in self._rules:
            if rid == rule_id:
                return en
        return False

    # ----- evaluation ---------------------------------------------------

    def evaluate(self, student: Student, hall: ExamHall) -> List[ConstraintViolation]:
        """
        Run every *enabled* rule for the given student–hall pair.
        Returns a list of violations (empty list ⇒ all constraints satisfied).
        """
        violations: List[ConstraintViolation] = []
        for _rid, _name, func, enabled in self._rules:
            if not enabled:
                continue
            v = func(student, hall)
            if v is not None:
                violations.append(v)
        return violations

    def evaluate_all_halls(
        self, student: Student, halls: List[ExamHall]
    ) -> Dict[str, List[ConstraintViolation]]:
        """Evaluate a student against every hall.  Returns {hall_name: [violations]}."""
        return {h.name: self.evaluate(student, h) for h in halls}

    # ----- introspection ------------------------------------------------

    def get_rules_info(self) -> List[Tuple[str, str, bool]]:
        """Return [(rule_id, display_name, enabled), …]."""
        return [(rid, name, en) for rid, name, _fn, en in self._rules]

    def get_rule_descriptions(self) -> List[str]:
        """Return human-readable description strings for all rules."""
        descriptions = {
            "R1": "A hall cannot exceed its seating capacity.",
            "R2": "A student's gender must match the hall's allowed-gender policy.",
            "R3": "If department mixing is not allowed, only one department per hall.",
            "R4": "Disabled students must be assigned to ground-floor halls.",
            "R5": "No two students with consecutive roll numbers on adjacent seats.",
        }
        result = []
        for rid, name, _fn, en in self._rules:
            status = "ENABLED" if en else "DISABLED"
            desc = descriptions.get(rid, "Custom rule.")
            result.append(f"[{rid}] {name} ({status})\n    {desc}")
        return result
