package tokenexposure.redact

redact_token(fp) := sprintf("tok_%s", [substr(fp, 0, 8)]) if fp != ""
