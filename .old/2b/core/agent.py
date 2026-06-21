import sys
import os

# Import pydantic BEFORE the platform hack to ensure sysconfig works correctly
from pydantic import BaseModel
from typing import List, Dict, Optional, Any, Type

# Workaround for llama-cpp-python platform check on Android/Termux
_orig_platform = sys.platform
if sys.platform == "android":
    sys.platform = "linux"

try:
    import outlines
    from outlines import models
    from llama_cpp import Llama
finally:
    sys.platform = _orig_platform

try:
    import numba
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False

from core.telemetry import telemetry

from core.schemas import ToolCall
import re
import json

class GemmaOutlinesAgent:
    """
    Gemma 2B Agent using Outlines 1.3.0 and llama-cpp-python backend.
    """
    def __init__(self, model_path: str, n_ctx: int = 8192, n_threads: int = 4):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found at {model_path}")
        
        # Initialize the llama-cpp model
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            verbose=False
        )
        # Wrap with Outlines
        self.model = outlines.from_llamacpp(self.llm)
        self.system_instructions: str = ""
        self.history: List[Dict[str, str]] = []
        self.session_id: str = "default"

    def set_system_instructions(self, instructions: str):
        self.system_instructions = instructions

    def format_prompt(self, message: str) -> str:
        """Formats the conversation history into the Gemma chat template."""
        prompt = ""
        full_history = self.history + [{"role": "user", "content": message}]
        
        for i, turn in enumerate(full_history):
            content = turn["content"]
            if i == 0 and self.system_instructions:
                content = f"{self.system_instructions}\n\n{content}"
            
            role = "user" if turn["role"] == "user" else "model"
            prompt += f"<start_of_turn>{role}\n{content}<end_of_turn>\n"
        
        prompt += "<start_of_turn>model\n"
        return prompt

    def generate_text(self, message: str, max_tokens: int = 1024, save_history: bool = False) -> str:
        """Generates raw text (unconstrained)."""
        prompt = self.format_prompt(message)
        generator = outlines.Generator(self.model)
        response = generator(prompt, max_tokens=max_tokens)
        
        telemetry.log(self.session_id, "llm_generate", {
            "prompt": prompt,
            "raw_output": response,
            "constrained": False
        })
        
        if save_history:
            self.history.append({"role": "user", "content": message})
            self.history.append({"role": "model", "content": response})
        return response

    def generate_json(self, message: str, schema: Type[BaseModel], max_tokens: int = 1024, save_history: bool = False) -> Any:
        """Generates structured data. Falls back to unconstrained if numba is missing."""
        global HAS_NUMBA
        prompt = self.format_prompt(message)
        
        response_obj = None
        content = ""
        raw_output = ""

        parsing_step = "constrained" if HAS_NUMBA and response_obj else "none"
        
        if HAS_NUMBA:
            try:
                generator = outlines.Generator(self.model, schema)
                response_obj = generator(prompt, max_tokens=max_tokens)
                if isinstance(response_obj, BaseModel):
                    content = response_obj.model_dump_json()
                    raw_output = content
                    parsing_step = "constrained"
                else:
                    content = str(response_obj)
                    raw_output = content
                    parsing_step = "constrained_str"
            except Exception as e:
                # Fallback on any error during constrained generation
                HAS_NUMBA = False # Disable for future calls in this session
                parsing_step = "failed_constrained"
        
        if response_obj is None:
            # Manual Fallback: Generate raw text and parse
            # Nudge the model by starting the JSON for it
            nudge = '{\n  "thought": "'
            prompt_with_nudge = prompt + nudge
            
            generator = outlines.Generator(self.model)
            raw_response = generator(prompt_with_nudge, max_tokens=max_tokens)
            raw_output = nudge + raw_response
            content = raw_output
            
            def repair_json(s):
                s = s.strip()
                if not s.startswith('{'):
                    match = re.search(r'\{.*', s, re.DOTALL)
                    if match:
                        s = match.group(0)
                    else:
                        return None
                
                # Balance quotes
                if s.count('"') % 2 != 0:
                    s += '"'
                
                # Balance braces
                open_braces = s.count('{')
                close_braces = s.count('}')
                if open_braces > close_braces:
                    s += '}' * (open_braces - close_braces)
                
                return s

            # Step 1: Look for JSON blocks inside markdown
            json_block_match = re.search(r"```json\s*(\{.*?\})\s*```", raw_output, re.DOTALL)
            if json_block_match:
                try:
                    data = json.loads(json_block_match.group(1))
                    response_obj = schema(**data)
                    parsing_step = "fallback_markdown_json"
                except:
                    pass

            if response_obj is None:
                # Step 2: Try to find any JSON-like structure
                # Find all { ... }
                matches = re.findall(r"(\{.*?\})", raw_output, re.DOTALL)
                for m in reversed(matches):
                    try:
                        data = json.loads(m)
                        if any(k in data for k in ["thought", "reasoning", "tool_name", "final_answer"]):
                            response_obj = schema(**data)
                            parsing_step = "fallback_inner_json"
                            break
                    except:
                        continue
            
            if response_obj is None:
                # Step 3: Final attempt, repair and parse
                repaired = repair_json(raw_output)
                if repaired:
                    try:
                        data = json.loads(repaired)
                        response_obj = schema(**data)
                        parsing_step = "fallback_repaired_json"
                    except:
                        # Try one more thing: if it's unclosed string in thought
                        try:
                            # Heuristic: if it ends with a quote that was added by repair_json, maybe it's still invalid
                            # Let's try to just close the last string value
                            if '": "' in repaired and not repaired.endswith('"}'):
                                # Find the last ": " and ensure it's closed
                                last_val_start = repaired.rfind('": "') + 4
                                if '"' not in repaired[last_val_start:-2]: # -2 to avoid the added "}
                                     # This is getting complex, let's try a simpler regex repair for unclosed strings
                                     pass
                        except:
                            pass
            
            if response_obj is None:
                # Step 4: Extreme Fallback - wrap raw output into the schema
                try:
                    fields = schema.model_fields.keys()
                    fallback_data = {}
                    if "thought" in fields:
                        # Clean up raw_output if it has the nudge
                        clean_output = raw_output
                        if clean_output.startswith('{\n  "thought": "'):
                            clean_output = clean_output[len('{\n  "thought": "'):]
                        fallback_data["thought"] = clean_output
                    
                    if "intent" in fields:
                        fallback_data["intent"] = "GENERAL"
                    
                    for field_name, field_info in schema.model_fields.items():
                        if field_name not in fallback_data:
                            if field_info.is_required():
                                fallback_data[field_name] = None if field_info.annotation is Optional else ""
                    
                    response_obj = schema(**fallback_data)
                    parsing_step = "extreme_fallback_wrap"
                except Exception as e:
                    response_obj = None
                    parsing_step = f"absolute_failure: {str(e)}"

        telemetry.log(self.session_id, "llm_generate", {
            "prompt": prompt,
            "raw_output": raw_output,
            "constrained": HAS_NUMBA,
            "parsing_step": parsing_step,
            "parsed_ok": not isinstance(response_obj, str)
        })

        if save_history:
            self.history.append({"role": "user", "content": message})
            self.history.append({"role": "model", "content": content})
        return response_obj

    def summarize(self, text: str) -> str:
        """Uses a high-density prompt to summarize text."""
        prompt = (
            f"<start_of_turn>user\n"
            f"Summarize the following conversation history into a dense, high-signal state log. "
            f"Keep all critical facts and tool observations.\n\n{text}<end_of_turn>\n"
            f"<start_of_turn>model\n"
        )
        generator = outlines.Generator(self.model)
        return generator(prompt, max_tokens=512)

    def extract_facts(self, text: str) -> List[str]:
        """Extracts a list of key facts from the text."""
        class FactList(BaseModel):
            facts: List[str]
            
        prompt = (
            f"<start_of_turn>user\n"
            f"Extract a list of key facts, results, and state changes from the following text. "
            f"Focus on information that is critical for future tasks.\n\n{text}<end_of_turn>\n"
            f"<start_of_turn>model\n"
        )
        # Use generate_json to get structured facts
        try:
            result = self.generate_json(prompt, FactList, save_history=False)
            if isinstance(result, FactList):
                return result.facts
            return []
        except:
            return []

    def clear_history(self):
        self.history = []
