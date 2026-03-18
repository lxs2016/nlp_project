"""
Hugging Face Spaces entrypoint for StoryWeaver (Gradio SDK).

Spaces will import this file and look for a Gradio app object (commonly named `demo`).
Local development can still use: python app_gradio.py
"""

import os

from app_gradio import build_ui

demo = build_ui()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "7860"))
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        css=getattr(demo, "_storyweaver_css", None),
    )

