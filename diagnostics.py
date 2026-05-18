class Diagnostic:

    def __init__(self, stage, message, token=None):
        self.stage = stage
        self.message = message
        self.token = token

    def __str__(self):

        if self.token:
            return (
                f"[{self.stage}] "
                f"{self.message} "
                f"near '{self.token[1]}'"
            )

        return f"[{self.stage}] {self.message}"


class DiagnosticEngine:

    def __init__(self):
        self.errors = []

    def report(self, stage, message, token=None):

        self.errors.append(
            Diagnostic(
                stage,
                message,
                token
            )
        )

    def has_errors(self):
        return len(self.errors) > 0

    def print_all(self):

        print("\n========= NOVA ERRORS =========\n")

        for error in self.errors:
            print(error)

        print(
            f"\n{len(self.errors)} error(s) found."
        )