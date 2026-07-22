# Output Examples

The first line of predictions.csv is:

sequence_id,t,predicted_state

The first line of posterior.csv is:

sequence_id,t,quiet_posterior,flow_limited_posterior,apnea_posterior,entropy

The first line of apnea_events.csv is:

sequence_id,start_t,end_t,length,mean_spo2_drop,max_resp_pause,mean_apnea_posterior,severity,preceding_state

The JSON files may include whitespace, but they must parse as JSON and use the field names from /app/docs/model-contract.md. In validation_metrics.json, confusion is an object keyed by true state, and each row is an object keyed by predicted state. Model and report numbers need enough significant digits for a 1e-9 numeric round trip.
