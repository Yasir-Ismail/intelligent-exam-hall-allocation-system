"""
reasoning_engine.py — CSP-Based Allocation Solver with Explanation Generation.

Models the exam-hall allocation as a Constraint Satisfaction Problem:
  • Variables  : students (each must be assigned a hall)
  • Domains    : available exam halls
  • Constraints: rules from the RuleEngine

The solver attempts to assign each student one by one.  When assignment
fails, it produces a rich ConflictReport with per-hall explanations and
human-readable resolution suggestions.
"""

from copy import deepcopy
from typing import Dict, List, Optional, Tuple

from models import (
    AllocationResult,
    AllocationStatus,
    ConstraintViolation,
    ExamHall,
    FloorLevel,
    Gender,
    Student,
)
from rule_engine import RuleEngine


# ═══════════════════════════════════════════════════════════════════════════
#  Conflict Explanation Builder
# ═══════════════════════════════════════════════════════════════════════════

def build_explanation(student: Student,
                      hall_violations: Dict[str, List[ConstraintViolation]]) -> str:
    """
    Produce a human-readable narrative explaining why the student could not
    be allocated to any hall.
    """
    lines = [f"Student {student.roll} (Dept: {student.department}, "
             f"Gender: {student.gender.value}, "
             f"Disabled: {'Yes' if student.disabled else 'No'}) "
             f"could not be assigned to any hall.\n"]
    lines.append("Evaluation details per hall:")
    lines.append("-" * 50)

    for hall_name, violations in hall_violations.items():
        if not violations:
            lines.append(f"  Hall {hall_name}: ALL constraints satisfied (unexpected conflict).")
        else:
            lines.append(f"  Hall {hall_name}:")
            for v in violations:
                lines.append(f"    ✗ [{v.rule_name}] {v.description}")

    lines.append("-" * 50)

    # Build a concise summary sentence
    hall_reasons = []
    for hall_name, violations in hall_violations.items():
        if violations:
            reasons = ", ".join(v.rule_name for v in violations)
            hall_reasons.append(f"Hall {hall_name} violated [{reasons}]")
    summary = "; ".join(hall_reasons) + "."
    lines.append(f"\nSummary: {summary}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  Resolution Suggestion Generator
# ═══════════════════════════════════════════════════════════════════════════

def generate_suggestions(student: Student,
                         hall_violations: Dict[str, List[ConstraintViolation]],
                         halls: List[ExamHall]) -> List[str]:
    """
    Analyse the specific constraint failures and produce targeted,
    human-like resolution suggestions.
    """
    suggestions: List[str] = []
    seen = set()

    # Collect unique violated rule names across all halls
    violated_rules: set = set()
    for vs in hall_violations.values():
        for v in vs:
            violated_rules.add(v.rule_name)

    # --- Capacity -------------------------------------------------------
    if "Capacity Constraint" in violated_rules:
        full_halls = [h for h in halls if h.remaining_capacity <= 0]
        hall_names = ", ".join(h.name for h in full_halls) if full_halls else "all halls"
        s = (f"Increase the capacity of one or more full halls ({hall_names}), "
             f"or add a new exam hall to accommodate additional students.")
        if s not in seen:
            suggestions.append(s)
            seen.add(s)

    # --- Gender ---------------------------------------------------------
    if "Gender Constraint" in violated_rules:
        s = (f"Add a hall that allows '{student.gender.value}' or 'Any' gender, "
             f"or change an existing hall's gender policy to 'Any'.")
        if s not in seen:
            suggestions.append(s)
            seen.add(s)

    # --- Department Mixing ----------------------------------------------
    if "Department Mixing Constraint" in violated_rules:
        non_mix_halls = [h.name for h in halls if not h.dept_mix_allowed]
        s = (f"Relax the department-mixing restriction for hall(s) "
             f"{', '.join(non_mix_halls)} to allow mixed departments, "
             f"or add a dedicated hall for the '{student.department}' department.")
        if s not in seen:
            suggestions.append(s)
            seen.add(s)

    # --- Disabled Accessibility -----------------------------------------
    if "Disabled Accessibility Constraint" in violated_rules:
        ground_halls = [h.name for h in halls if h.floor == FloorLevel.GROUND]
        if ground_halls:
            s = (f"Existing ground-floor hall(s) [{', '.join(ground_halls)}] may be "
                 f"full or have other constraint conflicts.  Consider increasing "
                 f"their capacity or adding another ground-floor hall for "
                 f"disabled students.")
        else:
            s = ("No ground-floor halls exist.  Add at least one ground-floor "
                 "exam hall to accommodate disabled students.")
        if s not in seen:
            suggestions.append(s)
            seen.add(s)

    # --- Anti-Cheating --------------------------------------------------
    if "Anti-Cheating (Adjacent Roll) Constraint" in violated_rules:
        s = ("Re-order the student processing sequence or shuffle seating "
             "within halls so consecutive-roll students are not adjacent.  "
             "Alternatively, relax the anti-cheating rule if acceptable.")
        if s not in seen:
            suggestions.append(s)
            seen.add(s)

    # --- Generic fallback -----------------------------------------------
    if not suggestions:
        suggestions.append(
            "Review the current hall configuration and rules.  "
            "Consider adding new halls or relaxing constraints."
        )

    return suggestions


# ═══════════════════════════════════════════════════════════════════════════
#  CSP Allocation Solver
# ═══════════════════════════════════════════════════════════════════════════

class AllocationSolver:
    """
    Constraint-Satisfaction-Problem solver for exam-hall allocation.

    Strategy (greedy with backtracking on anti-cheating):
      1. Sort students: disabled first, then by roll number.
      2. For each student, iterate over halls in order.
      3. Evaluate all rules.  If all pass → assign.
      4. If anti-cheating is the *only* failure, attempt to skip a seat
         (leave a gap) or try the next hall.
      5. If no hall works → record as Conflict with full explanation.
    """

    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine

    def solve(
        self,
        students: List[Student],
        halls: List[ExamHall],
    ) -> List[AllocationResult]:
        """
        Run the full allocation.  Returns an AllocationResult for every student.
        Halls' runtime state is mutated in-place.
        """
        # Reset hall states
        for h in halls:
            h.reset()

        # Sort: disabled students first (they have fewer valid halls),
        # then by roll number for deterministic ordering.
        sorted_students = sorted(
            students, key=lambda s: (not s.disabled, s.roll)
        )

        results: List[AllocationResult] = []

        for student in sorted_students:
            result = self._allocate_one(student, halls)
            results.append(result)

        # Re-sort results by roll for display consistency
        results.sort(key=lambda r: r.student.roll)
        return results

    # ----- single-student allocation ------------------------------------

    def _allocate_one(
        self, student: Student, halls: List[ExamHall]
    ) -> AllocationResult:
        """Try to place a single student into the best valid hall."""
        all_violations: Dict[str, List[ConstraintViolation]] = {}

        # Prioritise halls: prefer halls where the student's dept is
        # already present (reduces fragmentation), then by remaining capacity.
        prioritised = sorted(
            halls,
            key=lambda h: (
                student.department not in h.departments_present,
                -h.remaining_capacity,
            ),
        )

        for hall in prioritised:
            violations = self.rule_engine.evaluate(student, hall)
            all_violations[hall.name] = violations

            if not violations:
                # ✔ All constraints satisfied — assign
                return self._assign(student, hall)

            # Special handling: if only anti-cheating fails, try re-ordering
            if (len(violations) == 1
                    and violations[0].rule_name == "Anti-Cheating (Adjacent Roll) Constraint"):
                # Attempt to insert a gap by temporarily swapping the last
                # two assigned students (lightweight local repair).
                if self._try_anti_cheat_repair(student, hall):
                    return self._assign(student, hall)

        # ✗ No hall worked — Conflict
        explanation = build_explanation(student, all_violations)
        suggestions = generate_suggestions(student, all_violations, halls)

        # Flatten all violations into one list
        flat_violations = []
        for vs in all_violations.values():
            flat_violations.extend(vs)

        return AllocationResult(
            student=student,
            status=AllocationStatus.CONFLICT,
            violations=flat_violations,
            explanation=explanation,
            suggestions=suggestions,
        )

    # ----- assignment helper --------------------------------------------

    def _assign(self, student: Student, hall: ExamHall) -> AllocationResult:
        """Record a successful assignment."""
        seat = len(hall.assigned_students) + 1
        hall.assigned_students.append(student.roll)
        hall.departments_present.add(student.department)
        return AllocationResult(
            student=student,
            status=AllocationStatus.ALLOCATED,
            assigned_hall=hall.name,
            seat_number=seat,
        )

    # ----- anti-cheating local repair -----------------------------------

    def _try_anti_cheat_repair(self, student: Student, hall: ExamHall) -> bool:
        """
        Lightweight repair: check if placing a non-consecutive-roll student
        between the current last student and the new student would break
        the adjacency.  This is a heuristic — it may not always succeed.

        Returns True if, after the check, the constraint now passes.
        """
        if len(hall.assigned_students) < 2:
            return False

        # Check if swapping the last two would help
        # (This is a simple heuristic for the demo; a production system would
        #  use full CSP backtracking.)
        last = hall.assigned_students[-1]
        second_last = hall.assigned_students[-2]

        # Try swapping
        hall.assigned_students[-1], hall.assigned_students[-2] = second_last, last

        violations = self.rule_engine.evaluate(student, hall)
        if not violations:
            return True

        # Revert swap
        hall.assigned_students[-1], hall.assigned_students[-2] = last, second_last
        return False
