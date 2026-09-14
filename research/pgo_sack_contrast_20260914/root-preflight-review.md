# Independent preflight review

September 14, 2026, before any candidate fit. The root agent independently
reviewed the executable, sealed charter, algebra, gates, manifest members,
source pins, training preprocessing, saved-control replay and metric schema.
Verdict: **PASS to execute the declared experiment**.

The root replay matched all preflight fields except the ordering of the
protected-pins list when importing from a stdin process. The pin maps were
identical, with no changed, added or removed members. Execution will use the
same module CLI entrypoint as preparation. Independent metric arithmetic was
compatible, with maximum error 2.78e-17.

The instruction is to execute exactly nine once-only fits in exclusive
`run-attempt01`, retain every earlier attempt and all outcomes, then
independently verify serialized predictions, metrics and protected inputs.
There is no outcome-based retry and no production promotion. The reviewed
preflight, executable and tests remain unchanged.
