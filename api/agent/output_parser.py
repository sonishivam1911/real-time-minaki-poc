import json
import re

from json_repair import repair_json


class ActionParser:
    """
    Enhanced parser to extract actions from LLM output with json-repair integration.
    """

    def __init__(self, use_json_repair=True):
        """
        Initialize the parser.

        Args:
            use_json_repair: Whether to use json-repair library (requires installation)
        """
        self.use_json_repair = use_json_repair

    def safe_json_parse(self, json_str):
        """
        Enhanced JSON parser with json-repair integration and fallback strategies.

        Args:
            json_str: JSON string to parse

        Returns:
            Parsed JSON object or None if parsing fails
        """
        # Store original for debugging
        original_json = json_str.strip()

        # FIRST: Try to parse as-is (don't fix valid JSON!)
        try:
            return json.loads(original_json)
        except json.JSONDecodeError as e:
            print(
                f"[DEBUG] Initial parse failed at line {e.lineno}, col {e.colno}: {e.msg}"
            )
            print(
                f"[DEBUG] Error context: {repr(original_json[max(0, e.pos - 50) : e.pos + 50])}"
            )

        # SECOND: Try json-repair if available
        if self.use_json_repair:
            try:
                print("[DEBUG] Trying json-repair library...")
                repaired_json = repair_json(original_json)
                result = json.loads(repaired_json)
                print("[DEBUG] json-repair succeeded!")
                return result
            except Exception as e:
                print(f"[DEBUG] json-repair failed: {e}")
                # Continue to manual fixes

        # THIRD: Try minimal cleaning only
        try:
            # Remove BOM and normalize whitespace
            cleaned = original_json.replace("\ufeff", "").replace("\r\n", "\n")
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # FOURTH: Apply targeted fixes only if needed
        try:
            fixed_json = self.apply_targeted_fixes(original_json)
            print("[DEBUG] Trying with targeted fixes")
            return json.loads(fixed_json)
        except json.JSONDecodeError as e:
            print(f"[DEBUG] Targeted fixes failed: {e}")

        # FIFTH: Try extracting just the action_input if it's nested
        try:
            action_input_match = re.search(
                r'"action_input"\s*:\s*(\{[^{}]*\})', original_json, re.DOTALL
            )
            if action_input_match:
                action_input_json = action_input_match.group(1)
                # Try json-repair on the extracted part too
                if self.use_json_repair:
                    try:
                        action_input_json = repair_json(action_input_json)
                    except Exception:
                        pass
                action_input_data = json.loads(action_input_json)
                return {"action_input": action_input_data}
        except json.JSONDecodeError:
            pass

        # SIXTH: Last resort - try to extract any valid JSON object
        try:
            # Find the largest valid JSON object
            bracket_count = 0
            start_pos = original_json.find("{")
            if start_pos != -1:
                for i, char in enumerate(original_json[start_pos:], start_pos):
                    if char == "{":
                        bracket_count += 1
                    elif char == "}":
                        bracket_count -= 1
                        if bracket_count == 0:
                            # Found complete JSON object
                            candidate = original_json[start_pos : i + 1]
                            # Try json-repair on the candidate
                            if self.use_json_repair:
                                try:
                                    candidate = repair_json(candidate)
                                except Exception:
                                    pass
                            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        print(
            f"[DEBUG] All parsing attempts failed for JSON of length {len(original_json)}"
        )
        print(f"[DEBUG] First 200 chars: {repr(original_json[:200])}")
        return None

    def fix_unescaped_quotes(self, text):
        """Fix unescaped quotes within JSON strings"""
        result = []
        in_string = False
        i = 0

        while i < len(text):
            char = text[i]

            if char == '"' and (i == 0 or text[i - 1] != "\\"):  # Not escaped
                if not in_string:
                    # Starting a string
                    in_string = True
                    result.append(char)
                else:
                    # Ending a string - check if this is really the end
                    # Look for JSON delimiters after optional whitespace
                    next_chars = text[
                        i + 1 : i + 10
                    ].lstrip()  # Look ahead more characters
                    if (
                        next_chars.startswith((",", "]", "}", "\n"))
                        or next_chars == ""  # End of string
                        or next_chars.startswith(':"')  # Object key
                        or next_chars.startswith(": ")
                    ):  # Key-value separator
                        # This is likely the end of the string
                        in_string = False
                        result.append(char)
                    else:
                        # This is likely an unescaped quote within the string
                        result.append('\\"')
            else:
                result.append(char)
            i += 1

        return "".join(result)

    def apply_targeted_fixes(self, json_str):
        """
        Apply only necessary and safe fixes to JSON string.
        Note: This is now a fallback when json-repair is not available or fails.

        Args:
            json_str: JSON string that needs fixing

        Returns:
            Fixed JSON string
        """
        fixed = self.fix_unescaped_quotes(json_str)

        # Remove comments (major cause of JSON errors)
        fixed = re.sub(r"\s*//.*$", "", fixed, flags=re.MULTILINE)
        fixed = re.sub(r"/\*.*?\*/", "", fixed, flags=re.DOTALL)

        # Remove trailing commas
        fixed = re.sub(r",(\s*\])", r"\1", fixed)
        fixed = re.sub(r",(\s*\})", r"\1", fixed)

        # Fix missing quotes around simple object keys
        fixed = re.sub(r"\n\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\n    "\1":', fixed)

        # Add missing commas between array elements
        fixed = re.sub(r'"\s+(["\[\{])', r'", \1', fixed)

        # Add missing commas between object properties
        fixed = re.sub(r'"\s+"([a-zA-Z_])', r'", "\1', fixed)

        # Fix single quotes
        fixed = re.sub(r"'([^']*)':", r'"\1":', fixed)  # Keys
        fixed = re.sub(r":\s*'([^']*)'", r': "\1"', fixed)  # Values

        # Fix Python-style booleans and None
        fixed = re.sub(r"\bTrue\b", "true", fixed)
        fixed = re.sub(r"\bFalse\b", "false", fixed)
        fixed = re.sub(r"\bNone\b", "null", fixed)

        # Remove multiple consecutive commas
        fixed = re.sub(r",\s*,+", ",", fixed)

        # Fix missing closing quotes (conservative)
        lines = fixed.split("\n")
        fixed_lines = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if (
                stripped.startswith('"')
                and not stripped.endswith(('"', '",', '"]', '"}'))
                and ":" not in stripped
                and len(stripped) > 1
            ):
                line = line.rstrip() + '"'
            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def validate_json_brackets(self, json_str):
        """
        Quick validation of bracket/brace matching.

        Args:
            json_str: JSON string to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        stack = []
        pairs = {"[": "]", "{": "}"}

        in_string = False
        escape_next = False

        for i, char in enumerate(json_str):
            if escape_next:
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if not in_string:
                if char in pairs:
                    stack.append((char, i))
                elif char in pairs.values():
                    if not stack:
                        return False, f"Unexpected closing '{char}' at position {i}"
                    last_open, pos = stack.pop()
                    if pairs[last_open] != char:
                        return (
                            False,
                            f"Mismatched brackets: '{last_open}' at {pos} closed by '{char}' at {i}",
                        )

        if stack:
            unclosed = stack[-1]
            return False, f"Unclosed '{unclosed[0]}' at position {unclosed[1]}"

        return True, "Brackets are balanced"

    def parse_llm_output(self, llm_output: str):
        """
        Parse the LLM output to extract the action and action input.

        Args:
            llm_output: The raw output from the LLM

        Returns:
            Dictionary with action and action_input keys
        """
        # Default response structure - ALWAYS return dict for action_input
        response = {"action": "Final Answer", "action_input": {}}

        try:
            # Look for JSON in triple backticks first
            json_match = re.search(r"```json\s*(.*?)\s*```", llm_output, re.DOTALL)

            if json_match:
                json_str = json_match.group(1)
                print(f"[DEBUG] Found JSON in backticks, length: {len(json_str)}")
                parsed_json = self.safe_json_parse(json_str)

                if parsed_json and isinstance(parsed_json, dict):
                    if "action" in parsed_json:
                        response["action"] = parsed_json["action"]
                    if "action_input" in parsed_json:
                        action_input = parsed_json["action_input"]
                        # Ensure action_input is always a dict
                        if not isinstance(action_input, dict):
                            action_input = {"value": str(action_input)} if action_input else {}
                        response["action_input"] = action_input
                    return response

            # Look for complete JSON object by finding matching braces
            # This handles nested arrays, objects, etc.
            start_idx = llm_output.find('{')
            if start_idx != -1:
                brace_count = 0
                end_idx = -1
                
                for i in range(start_idx, len(llm_output)):
                    if llm_output[i] == '{':
                        brace_count += 1
                    elif llm_output[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i + 1
                            break
                
                if end_idx != -1:
                    json_str = llm_output[start_idx:end_idx]
                    print(f"[DEBUG] Found JSON object, length: {len(json_str)}")
                    parsed_json = self.safe_json_parse(json_str)

                    if parsed_json and isinstance(parsed_json, dict):
                        if "action" in parsed_json:
                            response["action"] = parsed_json["action"]
                        if "action_input" in parsed_json:
                            action_input = parsed_json["action_input"]
                            # Ensure action_input is always a dict
                            if not isinstance(action_input, dict):
                                action_input = {"value": str(action_input)} if action_input else {}
                            response["action_input"] = action_input
                        return response

            # Fallback: extract action from text patterns
            action_match = re.search(r'"?action"?\s*[:=]\s*"?([^"\']+)"?', llm_output)
            if action_match:
                response["action"] = action_match.group(1).strip()
            # action_input stays as empty dict {}

        except Exception as e:
            print(f"[DEBUG] Exception in parse_llm_output: {e}")
            response["action"] = "Final Answer"
            response["action_input"] = {"error": str(e)}

        return response

    def update_state_from_action(self, state, parsed_action):
        """
        Update the state based on the parsed action.

        Args:
            state: Current state dictionary
            parsed_action: The parsed action from the LLM output

        Returns:
            Updated state dictionary
        """
        action = parsed_action.get("action", "")
        action_input = parsed_action.get("action_input", {})

        # Convert string action_input to dict if needed
        if isinstance(action_input, str) and action in [
            "reconciliation_insights",
            "comprehensive_resource_analysis",
        ]:
            try:
                # Try json-repair first if available
                if self.use_json_repair:
                    try:
                        action_input = repair_json(action_input)
                        action_input = json.loads(action_input)
                    except Exception:
                        action_input = json.loads(action_input)
                else:
                    action_input = json.loads(action_input)
            except Exception:
                action_input = {"insights": [action_input]}

        # Enforce workflow stages
        if action == "Final Answer" or not action:
            if not state.get("current_item_type"):
                action = "item_type"
                action_input = {"user_query": state.get("input", "")}
            elif not state.get("schema_executed"):
                action = "item_schema"
                action_input = {"item_type": state.get("current_item_type")}
            elif state.get("schema_executed") and not state.get("data_executed"):
                action = "item_data"
                action_input = {"item_type": state.get("current_item_type")}

        # Update state based on action
        if action == "item_type":
            state["current_stage"] = "item_type"
            action_input["user_query"] = state.get("input")
        elif action == "item_schema":
            if isinstance(action_input, dict) and "item_type" in action_input:
                state["current_item_type"] = action_input["item_type"]
            state["current_stage"] = "schema"
        elif action == "item_data":
            if not state.get("current_item_type") and isinstance(action_input, dict):
                state["current_item_type"] = action_input.get("item_type")
            state["current_stage"] = "data"
        elif action == "item_efficiency":
            state["current_stage"] = "efficiency"
        elif action == "Final Answer":
            state["current_stage"] = "final"

        state["parsed_action"] = parsed_action
        return state