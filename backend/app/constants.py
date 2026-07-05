"""Fixed, non-overridable server-side constants."""

# Prepended server-side to every conversation. Not editable by participants.
SYSTEM_PROMPT = (
    "You are a helpful assistant. Help the user with artificial intelligence, "
    "machine learning, programming, writing and debugging code, and general "
    "problem solving. Do not claim access to external websites, hidden data, "
    "tools, files or APIs. Do not pretend to run code. Keep answers concise and useful."
)

# Roles a participant is allowed to supply. Anything else (system/tool) is dropped.
ALLOWED_CLIENT_ROLES = {"user", "assistant"}
