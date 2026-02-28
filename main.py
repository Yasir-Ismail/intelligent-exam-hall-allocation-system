import sys
import os

# Ensure the project root is on the path (useful when running from IDE).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui import ExamAllocatorApp


def main():
    app = ExamAllocatorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
