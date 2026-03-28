import re

class OutputGuardrail:
    def validate_response(self, response_text, tool_data):
        issues = self.check_structured_claims(response_text, tool_data)
        if issues:
            return False, f"Potential data mismatch: {issues}"
        return True, "OK"

    def check_structured_claims(self, response_text, tool_data):
        numeric_fields = self._flatten_numeric_fields(tool_data)
        if not numeric_fields:
            return []

        claims = self._extract_structured_claims(response_text)
        if not claims:
            return []

        issues = []
        for label, num in claims:
            if num <= 7.0:
                continue

            data_value = self._best_match_value(label, numeric_fields)
            if data_value is None:
                data_value = self._match_by_value(num, numeric_fields)
                if data_value is None:
                    issues.append(f"{label}={num} has no matching source field")
                    continue

            if not self._is_close(num, data_value):
                issues.append(f"{label}={num} mismatches source value {data_value}")

        return issues

    def _extract_structured_claims(self, response_text):
        claims = []
        patterns = [
            r'([A-Za-z_][A-Za-z_\s]{1,40})\s*[:=]\s*(-?\d+(?:,\d+)*(?:\.\d+)?)',
            r'([A-Za-z_][A-Za-z_\s]{1,40})\s+(?:is|was|at|of)\s+(-?\d+(?:,\d+)*(?:\.\d+)?)',
        ]
        for pattern in patterns:
            for label, number in re.findall(pattern, response_text):
                claims.append((self._normalize_label(label), float(number.replace(",", ""))))
        return claims

    def _flatten_numeric_fields(self, data, prefix=""):
        fields = {}
        if isinstance(data, dict):
            for k, v in data.items():
                nested_prefix = f"{prefix}.{k}" if prefix else str(k)
                fields.update(self._flatten_numeric_fields(v, nested_prefix))
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                nested_prefix = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
                fields.update(self._flatten_numeric_fields(item, nested_prefix))
        elif isinstance(data, (int, float)):
            fields[self._normalize_label(prefix)] = float(data)
        return fields

    def _normalize_label(self, label):
        return re.sub(r'[^a-z0-9]+', ' ', label.lower()).strip()

    def _best_match_value(self, claim_label, numeric_fields):
        if claim_label in numeric_fields:
            return numeric_fields[claim_label]

        # Fallback: token overlap for natural-language labels.
        claim_tokens = set(claim_label.split())
        best_score = 0.0
        best_value = None
        for field_label, value in numeric_fields.items():
            field_tokens = set(field_label.split())
            if not field_tokens:
                continue
            score = len(claim_tokens.intersection(field_tokens)) / len(field_tokens)
            if score > best_score:
                best_score = score
                best_value = value
        if best_score >= 0.5:
            return best_value
        return None

    def _is_close(self, observed, expected):
        if expected == 0:
            return observed == 0
        return abs(observed - expected) / abs(expected) <= 0.05

    def _match_by_value(self, observed, numeric_fields):
        for value in numeric_fields.values():
            if self._is_close(observed, value):
                return value
        return None
