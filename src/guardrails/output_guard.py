import re

class OutputGuardrail:
    def validate_response(self, response_text, tool_data):
        issues = self.check_numbers(response_text, tool_data)
        if issues:
            return False, f"Potential data mismatch: {issues}"
        return True, "OK"

    def check_numbers(self, response_text, tool_data):
        # Extract floats and ints using a regex
        matches = re.findall(r'\b\d+(?:,\d+)*(?:\.\d+)?\b', response_text)
        
        response_numbers = []
        for m in matches:
            clean = m.replace(",", "")
            try:
                response_numbers.append(float(clean))
            except ValueError:
                pass
                
        data_numbers = self._flatten_numbers(tool_data)
        
        issues = []
        for num in response_numbers:
            # Ignore binary/small/time indicator numbers
            if num <= 7.0: 
                continue
                
            match_found = False
            for dnum in data_numbers:
                if dnum != 0 and abs(num - float(dnum)) / abs(float(dnum)) <= 0.05:
                    match_found = True
                    break
                elif dnum == 0 and num == 0:
                    match_found = True
                    break
                    
            if not match_found:
                issues.append(f"{num} not found in source data")
                
        return issues
        
    def _flatten_numbers(self, data):
        nums = []
        if isinstance(data, dict):
            for v in data.values():
                nums.extend(self._flatten_numbers(v))
        elif isinstance(data, list):
            for item in data:
                nums.extend(self._flatten_numbers(item))
        elif isinstance(data, (int, float)):
            nums.append(float(data))
        return nums
