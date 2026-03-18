"""
Hugging Face Spaces entrypoint for StoryWeaver (Gradio SDK).

Spaces will import this file and look for a Gradio app object (commonly named `demo`).
Local development can still use: python app_gradio.py
"""

from app_gradio import build_ui

demo = build_ui()

