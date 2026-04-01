import sys

text = open("docs/api/openapi.yaml").read()
corrupted = '''      description: |\n        Extracts requirement spec from chat messages using the ClarificationEngine.\n        The engine invokes `LLMPort` underneath (Mock, Google, OpenAI depending on `~/.workflow/config.toml`).'''
correct = '''      description: |\n        A single structured clarification question returned by the ClarificationEngine.\n        Frontend renders each question according to its input_type.'''
text = text.replace(corrupted, correct)

# ensure we also update the original config.yaml we missed (the description was around line 264 earlier)
# Wait, I originally searched config.yaml and it didn't find anything because there wasn't one?
# The spec was: Update docs/api/openapi.yaml and any other spec references from config.yaml -> config.toml
# My python -c script replaced all config.yaml with config.toml anywhere. So we are good.

open("docs/api/openapi.yaml", "w").write(text)
