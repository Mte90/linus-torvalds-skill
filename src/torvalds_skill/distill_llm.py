"""
LLM API interaction logic for the distillation process.

Contains functions for calling the LLM, detecting truncation, and patching
truncated outputs.
"""

import json
import time
import urllib.request
import urllib.error
import sys

from . import config
from .distill_prompts import DISTILL_SYSTEM_PROMPT


def _detect_truncation(text: str, model: str) -> bool:
    """Detect if LLM output is truncated mid-sentence or mid-section.

    Returns True if the output appears incomplete:
    - Ends without proper closing (no terminal punctuation, no code fence close)
    - Token count is suspiciously low (< 500 for skill, < 800 for soul)
    - For GLM5.2: also checks for mid-word endings
    """
    if not text or not text.strip():
        return True

    stripped = text.strip()
    
    # Check token count threshold
    # Rough estimate: 1 token ≈ 4 characters
    token_count = len(stripped) / 4
    is_skill = "skill" in model.lower() or "distill" in model.lower()
    is_soul = "soul" in model.lower()
    
    min_tokens = 500 if is_skill else (800 if is_soul else 500)
    if token_count < min_tokens:
        return True

    # For GLM5.2, be stricter — must end with punctuation or code fence or section marker
    if "glm" in model.lower():
        if (stripped.endswith(".") or stripped.endswith("!") or 
            stripped.endswith("?") or stripped.endswith("```") or
            stripped.endswith("---")):
            return False  # Proper ending
        # Doesn't end properly for GLM
        return True
    
    # General check for other models
    proper_endings = (".", "!", "?", "```", "---", "##", "#")
    if any(stripped.endswith(ending) for ending in proper_endings):
        return False
    
    # Check if it ends mid-sentence (last word has no punctuation)
    words = stripped.split()
    if words:
        last_word = words[-1]
        # If last word doesn't end with punctuation and isn't a code element
        if not any(last_word.endswith(p) for p in (".", "!", "?", ")", "]", "`")):
            return True
    
    return False


def _patch_truncated_section(primary_text: str, fallback_text: str) -> str:
    """Merge truncated primary output with fallback tail.

    Finds the last complete section boundary in primary text, then appends
    everything after that point from the fallback output.
    """
    if not primary_text or not fallback_text:
        return fallback_text or primary_text or ""

    # Find section boundaries (markdown headers or --- separators)
    section_patterns = ["\n## ", "\n# ", "\n---", "\n### "]
    
    last_boundary_pos = 0
    for pattern in section_patterns:
        pos = primary_text.rfind(pattern)
        if pos > last_boundary_pos:
            last_boundary_pos = pos
    
    # If we found a boundary, extract the tail from fallback
    if last_boundary_pos > 0:
        # Get the section header from primary
        section_header = primary_text[last_boundary_pos:last_boundary_pos + 10].strip()
        
        # Find the same section in fallback
        fallback_section_pos = fallback_text.find(section_header)
        if fallback_section_pos != -1:
            # Check if fallback has more content after this section
            primary_tail = primary_text[last_boundary_pos:]
            fallback_tail = fallback_text[fallback_section_pos:]
            
            # If fallback is longer, append the difference
            if len(fallback_tail) > len(primary_tail):
                # Find where they diverge
                divergence = 0
                for i in range(min(len(primary_tail), len(fallback_tail))):
                    if primary_tail[i] != fallback_tail[i]:
                        divergence = i
                        break
                else:
                    divergence = len(primary_tail)
                
                # Append the missing part
                return primary_text[:last_boundary_pos + divergence] + fallback_tail[divergence:]
    
    # No clear section match, just return fallback
    return fallback_text


def _call_llm(prompt: str, retries: int = None, model: str = None, system_prompt: str = None) -> str:
    """Call the LLM for the distillation step. Returns raw text.

    Uses SSE streaming so reasoning models (e.g. GLM5.2) that spend minutes
    on internal reasoning don't hit read timeouts — each token delta keeps
    the connection alive.

    Implements fallback chain for GLM5.2 truncation:
    mistral-small-4-119b → gpt-oss-120b → glm5.2
    """
    from . import config
    
    retries = retries if retries is not None else config.MAX_RETRIES
    sys_prompt = system_prompt if system_prompt is not None else DISTILL_SYSTEM_PROMPT

    # Fallback model chain for truncation recovery
    fallback_models = ["mistral-small-4-119b", "gpt-oss-120b", "glm5.2"]
    primary_model = model or config.MODEL
    
    # Try primary model first, then fallbacks if truncation detected
    models_to_try = [primary_model]
    if primary_model not in fallback_models:
        models_to_try.extend(fallback_models)
    
    last_err = None
    primary_result = None
    
    for call_model in models_to_try:
        is_glm = "glm" in call_model.lower()
        
        payload = {
            "model": call_model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 16000,
            "stream": True,
        }
        
        # GLM5.2 is a reasoning model — needs 20 min for 16K-token generation.
        # Large prompts (souls, full-corpus distillation) also need long timeouts;
        # streaming keeps the connection alive.
        timeout = 1200 if is_glm else (600 if len(prompt) > 50_000 else 120)
        model_retries = retries
        
        for attempt in range(model_retries):
            try:
                body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    config.CHAT_URL,
                    data=body,
                    headers=config.headers(),
                    method="POST",
                )
                content_parts = []
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    for raw in resp:
                        line = raw.decode("utf-8").strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        text = delta.get("content")
                        if text:
                            content_parts.append(text)
                result = "".join(content_parts)
                if not result.strip():
                    last_err = RuntimeError("empty_response")
                    break
                
                # Check for truncation
                if _detect_truncation(result, call_model):
                    print(f"warning: truncation detected with {call_model}, trying fallback...", file=sys.stderr)
                    if primary_result is None:
                        primary_result = result
                    last_err = RuntimeError("truncation detected")
                    break
                
                # Success - no truncation
                if call_model != primary_model:
                    print(f"info: fallback model {call_model} succeeded", file=sys.stderr)
                    # Try to patch if we have a primary result
                    if primary_result is not None:
                        return _patch_truncated_section(primary_result, result)
                return result
                
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
                last_err = e
                time.sleep(config.RETRY_DELAY * (attempt + 1))
    
    # All models failed or truncated
    if primary_result is not None:
        print("warning: all models truncated, returning primary result", file=sys.stderr)
        return primary_result
    
    raise RuntimeError(f"LLM distill failed after {retries} retries: {last_err}")