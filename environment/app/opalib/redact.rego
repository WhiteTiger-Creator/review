package tokenexposure.redact

import rego.v1

redact_token(fp) := out if {
	fp != ""
	out := sprintf("tok_%s", [substring(fp, 0, 8)])
}
