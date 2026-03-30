from src.memory.store import ShortTermStore, LongTermStore, SemanticStore
from src.utils import database
import json
import re

MAX_FACTS_PER_RESPONSE = 20
FACT_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_\- ]{1,64}$")
FACT_EXTRACTION_EVERY_N_ASSISTANT_TURNS = 3

class MemoryManager:
    def __init__(self):
        self.short_term = ShortTermStore()
        self.long_term = LongTermStore()
        self.semantic = SemanticStore()

    def build_context(self, session_id):
        parts = []

        semantic_context = self.semantic.format_for_context()
        if semantic_context:
            parts.append(semantic_context)

        summary = self.long_term.get(session_id)
        if summary:
            parts.append(f"Conversation summary so far:\n{summary}")

        recent = self.short_term.get(session_id)

        return {
            "system_context": "\n\n".join(parts),
            "recent_messages": recent
        }

    def save_turn(self, session_id, user_msg, assistant_msg):
        self.short_term.save(session_id, "user", user_msg)
        self.short_term.save(session_id, "assistant", assistant_msg)

    def maybe_summarise(self, session_id, llm):
        full_history = database.get_full_history(session_id)
        
        if len(full_history) < 20: 
            return
            
        existing_summary = self.long_term.get(session_id)
        
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in full_history[-10:]])
        
        prompt = f"""
        You are summarising a fitness coaching conversation.
        Existing summary: {existing_summary or 'None'}
        New messages: {history_text}
        Write a concise updated summary capturing key insights, goals, and patterns discussed.
        """
        
        new_summary = llm.invoke(prompt).content
        self.long_term.save(session_id, new_summary)

    def should_extract_facts(self, session_id, every_n: int = FACT_EXTRACTION_EVERY_N_ASSISTANT_TURNS) -> bool:
        """Throttle fact extraction to every N assistant turns to reduce extra LLM calls."""
        safe_n = max(1, int(every_n))
        history = database.get_full_history(session_id)
        assistant_turns = sum(1 for msg in history if msg.get("role") == "assistant")
        if assistant_turns == 0:
            return False
        return assistant_turns % safe_n == 0
        
    def extract_and_store_facts(self, assistant_response, llm):
        prompt = f"""
        Given this fitness coaching response:
        {assistant_response}

        Extract any persistent facts about the user (injuries, goals, preferences, baselines).
        Return purely valid JSON with string keys and string values: {{"key": "value"}}. 
        Return empty {{}} if none. Do not include markdown blocks.
        """
        
        result_text = llm.invoke(prompt).content.strip()
        
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        result_text = result_text.strip()
        
        try:
            facts = json.loads(result_text)
            if not isinstance(facts, dict):
                return

            accepted = 0
            for key, value in facts.items():
                if accepted >= MAX_FACTS_PER_RESPONSE:
                    break
                if not isinstance(key, str):
                    continue
                key_clean = key.strip().lower()
                if not FACT_KEY_PATTERN.match(key_clean):
                    continue
                if isinstance(value, (dict, list)):
                    continue

                self.semantic.upsert(key_clean, str(value))
                accepted += 1
        except Exception:
            pass
