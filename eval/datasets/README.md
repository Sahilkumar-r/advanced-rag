# Golden set format
One JSON object per line in `golden.jsonl`:
`{"id","question","type","expected_pages":[],"reference_answer","answerable":true,"source":"hand|synthetic","reviewed":true}`
`type` is one of: lookup, how-to, multi-hop, comparison, code, off-topic, adversarial, image, voice.
Hand written cases are never overwritten by generated ones. Synthetic cases must be reviewed before they count.
No data yet: the 30 questions from rag-demo are imported in phase 0.
