"""Local Email Tracking and Application Status Ingestion Module."""

from .classifier import EmailClassifier
from .imap_client import ImapEmailClient
from .syncer import EmailSyncManager, load_email_config, save_email_config

__all__ = [
    "EmailClassifier",
    "ImapEmailClient",
    "EmailSyncManager",
    "load_email_config",
    "save_email_config"
]
