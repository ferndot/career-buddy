"""The providers the settings page offers. Cloud URLs are fixed so a cloud key cannot be sent to another host."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Preset:
    id: str
    label: str
    base_url: str
    url_editable: bool
    needs_key: bool
    off_device: bool
    hint: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


DOCKER = " In Docker, use host.docker.internal instead of localhost."
PRESETS: tuple[Preset, ...] = (
    Preset("anthropic", "Anthropic", "https://api.anthropic.com/v1", False, True, True,
           "Get a key at console.anthropic.com. Your resume text is sent to Anthropic."),
    Preset("gemini", "Google AI Studio", "https://generativelanguage.googleapis.com/v1beta/openai", False, True, True,
           "Get a key at aistudio.google.com. Your resume text is sent to Google."),
    Preset("ollama", "Ollama", "http://localhost:11434/v1", True, False, False, "Start Ollama first." + DOCKER),
    Preset("lmstudio", "LM Studio", "http://localhost:1234/v1", True, False, False, "Turn on the local server in LM Studio first." + DOCKER),
    Preset("llamacpp", "llama.cpp", "http://localhost:9931/v1", True, False, False,
           "Uses port 9931. The llama.cpp Docker image uses 8080." + DOCKER),
    Preset("custom", "Custom URL", "", True, False, False, "Any server that speaks the OpenAI chat format. Add a key only if it asks for one."),
)
BY_ID = {p.id: p for p in PRESETS}
