"""
Hugging Face Spaces entrypoint for StoryWeaver (Gradio SDK).

Spaces will import this file and look for a Gradio app object (commonly named `demo`).
Local development can still use: python app_gradio.py
"""

import os

from app_gradio import build_ui

demo = build_ui()

if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        ssr_mode=False,
        css=getattr(demo, "_storyweaver_css", None),
    )

