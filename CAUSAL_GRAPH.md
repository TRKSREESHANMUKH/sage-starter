# Project SAGE — Expert Causal Graph (DAG)

> **Research Framing**:
> *"SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."*

---

## 🧭 How to View This Graph in VS Code

You have **3 convenient ways** to view this graph directly inside VS Code:

### Option 1: Native Markdown Preview (Quickest & Crisp Vector)
1. Open this file ([`CAUSAL_GRAPH.md`](file:///Users/asl/Desktop/sage-starter/CAUSAL_GRAPH.md)) in VS Code.
2. Press **`Cmd + Shift + V`** (or **`Cmd + K V`** for side-by-side preview).
   *(On Windows/Linux: `Ctrl + Shift + V` or `Ctrl + K V`)*
3. VS Code renders the **Mermaid diagram below automatically** as a high-resolution flowchart.

### Option 2: Image Preview in Editor Tab
1. In the VS Code File Explorer (left sidebar), click:  
   👉 [`analytics/causal_graph.png`](file:///Users/asl/Desktop/sage-starter/analytics/causal_graph.png) *(or [`causal_graph.svg`](file:///Users/asl/Desktop/sage-starter/analytics/causal_graph.svg))*
2. VS Code will open the 300-DPI color-coded architectural diagram directly in an editor tab.

### Option 3: Interactive Visualizer (Pan, Zoom, Click-to-Inspect)
1. Open [`analytics/causal_graph.html`](file:///Users/asl/Desktop/sage-starter/analytics/causal_graph.html).
2. Right-click and choose **"Open with Live Server"** or open in your browser, or:
3. In VS Code, press **`Cmd + Shift + P`** &rarr; Type **`Simple Browser: Show`** &rarr; Enter:  
   `file:///Users/asl/Desktop/sage-starter/analytics/causal_graph.html`
4. Click any node to see its parents, children, and operational description in the sidebar!

---

## 📊 Live Mermaid Diagram (VS Code Renderable)

```mermaid
graph LR
    %% Styles
    classDef exo fill:#0284c7,stroke:#38bdf8,stroke-width:2px,color:#fff;
    classDef mat fill:#ea580c,stroke:#fdba74,stroke-width:2px,color:#fff;
    classDef dem fill:#be185d,stroke:#f472b6,stroke-width:2px,color:#fff;
    classDef prod fill:#15803d,stroke:#4ade80,stroke-width:2px,color:#fff;
    classDef fg fill:#ca8a04,stroke:#fde047,stroke-width:2px,color:#fff;
    classDef target fill:#b91c1c,stroke:#f87171,stroke-width:3px,color:#fff;

    subgraph Tier0 ["Tier 0: Exogenous Inbound & Calendar"]
        s1_del["S1 PO Delay"]:::exo
        s1_fill["S1 Fill Rate"]:::exo
        s2_del["S2 PO Delay"]:::exo
        s2_fill["S2 Fill Rate"]:::exo
        s3_del["S3 PO Delay"]:::exo
        s3_fill["S3 Fill Rate"]:::exo
        s4_del["S4 PO Delay"]:::exo
        s4_fill["S4 Fill Rate"]:::exo
        s5_del["S5 PO Delay"]:::exo
        s5_fill["S5 Fill Rate"]:::exo
        wday["weekday"]:::exo
        mon["month"]:::exo
        p201_plan["P201 Plan"]:::exo
        p201_short["P201 Shortfall"]:::exo
        p202_plan["P202 Plan"]:::exo
        p202_short["P202 Shortfall"]:::exo
    end

    subgraph Tier1 ["Tier 1: Raw Materials"]
        m101_lag["Mat 101 Lag"]:::mat
        m101["Mat 101 Stock (Steel)"]:::mat
        m102_lag["Mat 102 Lag"]:::mat
        m102["Mat 102 Stock (Plastic)"]:::mat
        m103_lag["Mat 103 Lag"]:::mat
        m103["Mat 103 Stock (Copper)"]:::mat
    end

    subgraph Tier2 ["Tier 2: Customer Demand"]
        p201_dem["P201 Demand"]:::dem
        p202_dem["P202 Demand"]:::dem
    end

    subgraph Tier3 ["Tier 3: Factory Production (BOM)"]
        p201_act["P201 Actual Production"]:::prod
        p202_act["P202 Actual Production"]:::prod
    end

    subgraph Tier4 ["Tier 4: Finished Goods Warehouse"]
        p201_fg_lag["P201 FG Lag"]:::fg
        p201_fg["P201 FG Stock"]:::fg
        p202_fg_lag["P202 FG Lag"]:::fg
        p202_fg["P202 FG Stock"]:::fg
    end

    subgraph Tier5 ["Tier 5: Customer Backlog (Target)"]
        p201_back["P201 Due Backlog"]:::target
        p202_back["P202 Due Backlog"]:::target
    end

    %% Material 101 Inflow
    m101_lag --> m101
    s1_del --> m101
    s1_fill --> m101
    s2_del --> m101
    s2_fill --> m101
    s4_del --> m101
    s4_fill --> m101

    %% Material 102 Inflow
    m102_lag --> m102
    s3_del --> m102
    s3_fill --> m102
    s4_del --> m102
    s4_fill --> m102

    %% Material 103 Inflow
    m103_lag --> m103
    s1_del --> m103
    s1_fill --> m103
    s5_del --> m103
    s5_fill --> m103

    %% Demand Seasonality
    wday --> p201_dem
    mon --> p201_dem
    wday --> p202_dem
    mon --> p202_dem

    %% Manufacturing BOM Constraints
    p201_plan --> p201_act
    p201_short --> p201_act
    m101 --> p201_act
    m102 --> p201_act
    m103 --> p201_act

    p202_plan --> p202_act
    p202_short --> p202_act
    m101 --> p202_act
    m103 --> p202_act

    %% Finished Goods Warehousing
    p201_fg_lag --> p201_fg
    p201_act --> p201_fg
    p201_dem --> p201_fg

    p202_fg_lag --> p202_fg
    p202_act --> p202_fg
    p202_dem --> p202_fg

    %% Order Backlog Generation
    p201_fg --> p201_back
    p201_dem --> p201_back
    p202_fg --> p202_back
    p202_dem --> p202_back
```

---

## 📋 Graph Architecture Specifications

- **Total Nodes**: 32 operational variables
- **Total Directed Edges**: 40 physical mechanisms
- **Graph Storage**: Serialized in [`stage7/fitted_causal_model.pkl`](file:///Users/asl/Desktop/sage-starter/stage7/fitted_causal_model.pkl)
- **Code Definition**: [`stage7/build_causal_model.py`](file:///Users/asl/Desktop/sage-starter/stage7/build_causal_model.py)
