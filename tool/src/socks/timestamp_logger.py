import pathlib
import csv
import time
from contextlib import contextmanager


class Timestamp_Logger:
    """
    A class to log timestamps in csv files
    """

    def __init__(self, log_file: pathlib.Path):
        # Log file to store timestamps
        self._log_file = log_file

    def log_timestamp(self, identifier: str):
        """
        Creates or updates a timestamp in a timestamp csv file.

        Args:
            identifier:
                Identifier of the timestamp.

        Returns:
            None

        Raises:
            None
        """

        logs = []
        log_found = False
        timestamp = time.time()

        # Read the existing logs from the file (if it exists)
        try:
            with open(self._log_file, mode="r", newline="") as file:
                reader = csv.reader(file)
                logs = list(reader)
        except FileNotFoundError:
            # If the file doesn't exist, it will be created automatically later,
            # but it should be ensured here that the parent directory exists
            self._log_file.parent.mkdir(parents=True, exist_ok=True)

        # Check if we need to update an existing log with the identifier
        for i, row in enumerate(logs):
            if row[0] == identifier:
                logs[i] = [identifier, timestamp]
                log_found = True
                break

        # If the log was not found, create a new one
        if not log_found:
            logs.append([identifier, timestamp])

        # Write all logs back to the CSV file
        with open(self._log_file, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerows(logs)

    def get_logged_timestamp(self, identifier: str) -> float:
        """
        Reads a timestamp from a timestamp csv file.

        Args:
            identifier:
                Identifier of the timestamp.

        Returns:
            The timestamp if it was found. Otherwise 0.

        Raises:
            ValueError:
                If the identifier cannot be found in the file
        """

        timestamp = 0.0

        # Read the existing logs from the file
        try:
            with open(self._log_file, mode="r", newline="") as file:
                reader = csv.reader(file)
                logs = list(reader)
        except FileNotFoundError:
            return timestamp  # It is okay if the file does not exist

        # Find the timestamp
        for row in logs:
            if row[0] == identifier:
                timestamp = float(row[1])
                break

        return timestamp

    def del_logged_timestamp(self, identifier: str):
        """
        Delete a timestamp in a timestamp csv file.

        Args:
            identifier:
                Identifier of the timestamp.

        Returns:
            None

        Raises:
            None
        """

        logs = []

        # Read the existing logs from the file (if it exists)
        try:
            with open(self._log_file, mode="r", newline="") as file:
                reader = csv.reader(file)
                logs = list(reader)
        except FileNotFoundError:
            return  # It is okay if the file does not exist

        # Check if we need to update an existing log with the identifier
        for i, row in enumerate(logs):
            if row[0] == identifier:
                del logs[i]

        # Write all logs back to the CSV file
        with open(self._log_file, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerows(logs)

    @contextmanager
    def timestamp(self, identifier: str):
        """
        A context manager to manage timestamp logging. E.g. if a timestamp is used to log the success of a function,
        it makes sense to remove the timestamp before the function is executed again, as the function could fail
        on the new attempt and the "success" timestamp could then be misleading.

        Args:
            identifier:
                Identifier of the timestamp.

        Returns:
            None

        Raises:
            None
        """

        # Reset function success log
        self.del_logged_timestamp(identifier=identifier)
        yield
        # If this point is reached, the nested block was successful -> Log success
        self.log_timestamp(identifier=identifier)