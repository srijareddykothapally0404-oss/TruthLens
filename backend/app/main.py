"""Project-root entry point for the TruthLens FastAPI application."""

from src.api import APISettings, CLASSIFIER_NAME, app, create_app

__all__ = ["APISettings", "CLASSIFIER_NAME", "app", "create_app"]
