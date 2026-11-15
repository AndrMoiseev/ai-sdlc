"""Count complete Kotlin parameter declarations retained in detekt messages.

Generic and function types, annotations and grouped defaults are nested syntax,
so only outer commas separate parameters. Unsupported or ambiguous syntax remains
unknown; the detector's threshold is never treated as an observed count.
"""

import re


def parameter_count(message):
    signature, separator, _ = message.rpartition(") has too many parameters.")
    if not separator or not signature.startswith(("The function ", "The constructor(")):
        return None
    opening = re.search(r"(?:`[^`]+`|[^(`])*\(", signature)
    if opening is None:
        return None
    text = signature[opening.end():]
    stack, count, start, index = [], 0, 0, 0
    typed, default = False, False
    while index < len(text):
        char = text[index]
        if text.startswith("//", index):
            end = text.find("\n", index)
            index = len(text) if end < 0 else end
            continue
        if text.startswith("/*", index):
            depth = 1
            index += len("/*")
            while index < len(text) and depth:
                if text.startswith("/*", index):
                    depth += 1
                    index += len("/*")
                elif text.startswith("*/", index):
                    depth -= 1
                    index += len("*/")
                else:
                    index += 1
            if depth:
                return None
            continue
        if char in ('"', "'", '`'):
            quote = '"""' if text.startswith('"""', index) else char
            index += len(quote)
            while index < len(text) and not text.startswith(quote, index):
                # Interpolated strings may contain nested quotes/expressions. Keep
                # those uncommon report forms unknown rather than guessing a count.
                if char == '"' and text.startswith('${', index):
                    return None
                if text[index] == '\\' and quote != '`':
                    index += 1
                index += 1
            if index >= len(text):
                return None
            index += len(quote)
            continue
        if char in "([{":
            stack.append({"(": ")", "[": "]", "{": "}"}[char])
        elif char in ")]}":
            if not stack or stack.pop() != char:
                return None
        elif char == '<':
            if not default:
                stack.append('>')
            elif not stack:
                return None  # A default comparison and a generic call are ambiguous here.
        elif char == '>' and (index == 0 or text[index - 1] != '-') and not default:
            if not stack or stack.pop() != '>':
                return None
        elif not stack:
            if char == ':':
                typed = True
            elif char == '=':
                default = True
            elif char == ',':
                if not typed or not text[start:index].strip():
                    return None
                count += 1
                start, typed, default = index + 1, False, False
        index += 1
    if stack:
        return None
    if text[start:].strip():
        return count + 1 if typed else None
    return count
