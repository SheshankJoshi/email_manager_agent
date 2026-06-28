from abc import ABC, abstractmethod

class EmailConnector(ABC):
    """Abstract base class for all email connectors."""
    @abstractmethod
    def connect(self) -> bool:
        """Establishes the connection to the email service."""
        pass

    @abstractmethod
    def list_inbox(self) -> list[dict]:
        """Retrieves the inbox items from the connected account."""
        pass

    @abstractmethod
    def manage_email(self, email_address: str, action: str, details: dict = None) -> dict:
        """Performs an action on the inbox."""
        pass