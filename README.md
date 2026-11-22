# SAGE: Supply Chain Attribution and Grounded Explanation

Author: TRK Sreeshanmukh
Specialization: Causal Machine Learning and Systems Engineering

### Why Causal AI for Supply Chains?

Modern factory Enterprise Resource Planning systems collect millions of transactional rows, yet operations managers remain stuck diagnosing delays through manual spreadsheet triage.

Correlation is symmetric, but supply chains are physical and directional. Consuming steel produces finished widgets, but producing widgets cannot magically create raw steel. 

SAGE bridges Judea Pearl's structural causal inference framework with real enterprise transaction ledgers. It converts passive factory telemetry into actionable, audit verifiable root cause explanations without generative AI hallucinations.

### What I Personally Designed and Built

1. The Expert Structural Causal Model
Mapped factory physics into a 32 node Directed Acyclic Graph enforcing strict Bill of Materials conservation. Parameterized linear structural equations to quantify path strengths between vendor delays, safety stock depletion, line bottlenecks, and delivery backlog.

2. Non Parametric Anomaly Scoring
Implemented robust anomaly detection using median absolute deviation statistics rather than mean variance formulas, preventing extreme industrial shocks from skewing detection thresholds.

3. The Backward Path Attribution Engine
Created the graph search routine that starts at unfulfilled delivery nodes and searches parent histories to distinguish intermediate propagation symptoms from original upstream causes.

4. Deterministic Natural Language Briefings
Constructed an evidence binding narration engine that translates mathematical causal paths into plain English briefings. Every vendor name, delayed unit count, and purchase order ID is strictly verified against database rows, ensuring zero hallucinations and zero leaked test keys.

### System Architecture Overview

• Core Causal Engine: Contains the expert graph topology and fitted structural equation parameters.
• Grounded Narration: Formats verified operational evidence into executive briefings.
• Operational Dispatch: Computes daily status snapshots and handles scheduled email delivery.
• Evaluation Suite: Benchmarks causal attribution against controlled operational scenarios.
• Web Viewer: Provides interactive causal DAG visualizers and inventory trend charts.
• Operator Console: Secure interface for manual simulation runs and system health checks.

### Key Validation Outcomes

• 95% Causal Attribution Accuracy across a continuous 10 day multi shock evaluation feed.
• Zero hallucinations verified by automated evidence packet scanning tests.
• Sub 2.5 second total runtime for daily metric aggregation, causal inference, and PDF document generation on a standard CPU.
• Complete test coverage across 41 automated test suites.

### Running the System Locally

To launch both the Executive Viewer and the Operator Controller:
bash run_sage.sh

Local Dashboard URLs:
Viewer Interface: http://127.0.0.1:8000
Controller Console: http://127.0.0.1:8001/ctrl

Administrative Login:
Identifier: admin
Password: SageAdmin2026!

To stop the services cleanly:
bash stop_sage.sh
