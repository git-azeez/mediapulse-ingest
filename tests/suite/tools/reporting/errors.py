class VerifierError(Exception):
    """Base verifier exception."""


class SubmissionFailure(VerifierError):
    """The submission failed a published obligation."""


class AcceptedWriteLoss(SubmissionFailure):
    """An API-accepted command could not be recovered from durable state."""


class AuthEscalation(SubmissionFailure):
    """An identity performed an operation outside its published scope."""


class HarnessError(VerifierError):
    """The benchmark substrate failed independently of the submission."""


class CommandFailure(VerifierError):
    def __init__(self, message: str, *, returncode: int, stdout: str = "", stderr: str = ""):
        super().__init__(message)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class DeadlineExceeded(VerifierError):
    """A published polling deadline expired."""

    def __init__(self, message: str, *, stdout: str = "", stderr: str = ""):
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
