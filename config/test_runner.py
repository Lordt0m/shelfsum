from unittest import TextTestResult

from django.test.runner import DiscoverRunner


class NoSkipTextTestResult(TextTestResult):
    def addSkip(self, test, reason):
        error = AssertionError(f"Skipped test is not allowed in PostgreSQL CI: {reason}")
        self.addFailure(test, (AssertionError, error, None))


class NoSkipTestRunner(DiscoverRunner):
    def get_resultclass(self):
        return NoSkipTextTestResult
