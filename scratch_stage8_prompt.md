<USER_REQUEST>
# SAGE Stage 8: Ollama Narration Layer

## 0. Position and prerequisite

```
1-6  Simulator, incidents, ground truth, daily panel      [FROZEN]
7    Expert DAG + DoWhy GCM attribution                    [must be FROZEN first - see Stage 7 closure prompt]
8    Local-LLM narration of causal attribution results     <-- THIS STAGE
9    Reports + APScheduler + SMTP                          [NEXT]
```

Do not start Stage 8 until `stage7/FROZEN.json` exists. Do not modify Stages 1-7 or the 20-table schema.

## 1. What this stage is, and the rules that govern it

Stage 8 turns Stage 7's numeric attribution output into short, plain-language explanations a manager can read. The LLM is a **narrator, not an analyst**.

Hard rules (each one is enforced in code in section 7, not just stated):

1. The LLM never decides what caused something. Every cause it names must come from the evidence packet, which is built from Stage 7's raw scores by deterministic code.
2. Every number, date, supplier, material and product in a narrative must appear in the evidence packet.
3. The confidence tier is computed by code before the LLM is called. The LLM must write language that matches the tier. It may not upgrade it.
4. Ground truth never reaches the LLM. No `business_events` rows, no scenario ids, no incident types or names, no true-driver labels.
5. There is no RAG, no vector database, no chat interface, no agents, no tool calling and no frontend. This is a batch pipeline run from the terminal.
6. Research framing, used verbatim in outputs and docs: "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

## 2. Critical leakage trap (read before writing any code)

`analytics/scenario_causal_evaluation.csv` and `.json` contain the **true drivers read from `business_events`** and classification labels (for example "Strong Exogenous Attribution") that were decided using those drivers. **The packet builder must not read them.**

The
<truncated 10870 bytes>
w both outputs.
- Packet determinism: build packets twice and confirm identical bytes.

## 10. Do not

- Do not edit the Stage 1-7 code, DAG, thresholds, panels or schema.
- Do not use Strategy A' pooled rankings as the basis for tiers. Use the pre-registered primary rule from Stage 7.
- Do not add any retrieval, memory, chat or agent features.
- Do not tune tier thresholds or the prompt after viewing evaluation results. If a narrative is wrong because of a genuine bug, fix the bug and say so.
- Do not write to the Risks table. That belongs to Stage 9.
- Do not persist narratives to the database unless the existing intelligence-table columns fit without a migration. Default to files.

## 11. Execution order

1. Build packets, then print one packet and read it for any leaked label.
2. Pilot: generate one narrative for one packet, run the validators, read the result.
3. Only then run all 10.
4. Run the validators, then `evaluate_narratives.py`, then `test_stage8_leakage.py`.
5. Freeze: write `stage8/FROZEN.json` with hashes of packets, prompt, model digest and options.

## 12. Definition of done and what to send back

- All 10 narratives validate (first-attempt and final rates shown).
- The calibration criterion is 0 confidently-wrong narratives, or each exception is explained.
- Leakage tests pass with the mutation output shown.
- Send back: packets P01 (one packet in full), the 3 printed narratives, the validator results table, the evaluation table, the leakage test output, the model name and digest, and the list of any narratives that used the fallback.think properly and carefully and start
</USER_REQUEST>
<ADDITIONAL_METADATA>
The current local time is: 2026-10-10T12:13:10+05:30.
</ADDITIONAL_METADATA>
<USER_SETTINGS_CHANGE>
The user changed setting `Model Selection` from Gemini 3.6 Flash (High) to Claude Sonnet 4.6 (Thinking). No need to comment on this change if the user doesn't ask about it. If reporting what model you are, please use a human readable name instead of the exact string.
</USER_SETTINGS_CHANGE>