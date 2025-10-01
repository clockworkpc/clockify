"""
Client management functionality for Clockify CLI.
"""
from typing import List, Optional, Tuple
from .api_client import ClockifyAPI
from .config import ClockifyConfig
from .utils import get_user_selection


class ClientManager:
    """Handles client selection and management."""

    def __init__(self, api: ClockifyAPI, config: ClockifyConfig):
        self.api = api
        self.config = config

    def get_clients(self) -> List[dict]:
        """Get all clients from the workspace."""
        return self.api.get_clients()

    def get_client_names(self) -> List[str]:
        """Get list of client names."""
        clients = self.get_clients()
        return [client["name"] for client in clients]

    def find_client_by_name(self, name: str) -> Optional[dict]:
        """Find client by name."""
        clients = self.get_clients()
        for client in clients:
            if client["name"] == name:
                return client
        return None

    def find_client_by_id(self, client_id: str) -> Optional[dict]:
        """Find client by ID."""
        clients = self.get_clients()
        for client in clients:
            if client["id"] == client_id:
                return client
        return None

    def get_current_client(self) -> Optional[dict]:
        """Get the current client from config."""
        if self.config.client_id:
            client = self.find_client_by_id(self.config.client_id)
            if client:
                return client
        return None

    def get_current_client_name(self) -> Optional[str]:
        """Get the current client name."""
        client = self.get_current_client()
        return client["name"] if client else None

    def list_clients(self) -> None:
        """List all clients."""
        clients = self.get_clients()
        if not clients:
            print("No clients found")
            return

        print("Available Clients:")
        for client in clients:
            print(f"  {client['id']} - {client['name']}")

    def select_client_interactive(self) -> Optional[Tuple[str, str]]:
        """Interactively select a client."""
        clients = self.get_clients()
        if not clients:
            print("No clients found")
            return None

        client_names = [client["name"] for client in clients]
        current_client_name = self.get_current_client_name()

        selection_index = get_user_selection(
            client_names,
            "Available Clients",
            current_client_name
        )

        if selection_index is not None:
            selected_client = clients[selection_index]
            return selected_client["id"], selected_client["name"]

        return None

    def set_current_client(self, client_id: str) -> bool:
        """Set the current client in configuration."""
        client = self.find_client_by_id(client_id)
        if not client:
            print(f"Client with ID {client_id} not found")
            return False

        self.config.client_id = client_id
        print(f"Current client set to: {client['name']}")
        return True

    def set_current_client_by_name(self, client_name: str) -> bool:
        """Set the current client by name."""
        client = self.find_client_by_name(client_name)
        if not client:
            print(f"Client '{client_name}' not found")
            return False

        self.config.client_id = client["id"]
        print(f"Current client set to: {client['name']}")
        return True
