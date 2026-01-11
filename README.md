# SwarmSense: RAG-Powered USV Swarm Observability
**SwarmSense** is a prototype demonstration of a monitoring layer for Unmanned Surface Vehicle (USV) swarms. It is designed to bridge the gap between high-level mission oversight and low-level telemetry, allowing operators to manage large fleets while reducing cognitive load and improving decision-making.

> [!IMPORTANT] 
> **Project Scope:** This is a **technical demonstration** and proof-of-concept. It is designed to explore the application of Retrieval-Augmented Generation (RAG) in maritime robotics environments, focusing on reducing human cognitive load during swarm operations.

### The Problem: The Attention Bottleneck
As swarm operations scale, the human becomes the bottleneck. Traditional monitoring requires a technically-proficient operator to:
1. **Identify** which specific USV is experiencing an issue (e.g., GPS dropout).
2. **Diagnose** by manually sifting through logs and signal graphs.
3. **Correct** the issue while the rest of the swarm continues to operate unmonitored.

As the swarm grows, this manual overhead makes it impossible to maintain situational awareness, especially in high-stakes environments.

### The Solution: Intelligent Observability
SwarmSense transforms telemetry from a stream of logs into a **searchable, conversational knowledge base**. Instead of parsing raw logs, operators interact with the swarm as a collective intelligence.

### Key Capabilities
- **Natural Language Observability:** Query the swarm directly: *"Which units lost GPS in the last 5 minutes?"* or *"Why is Unit-04 deviating from formation?"*
- **Hierarchical Monitoring:** Quickly pivot from a 10,000-foot swarm overview to granular, individual USV behavior.
- **Contextual Insights:** The RAG engine reads mission plans and real-time logs to provide context-aware explanations, not just output raw data.

## Project Components
The system is divided into three parts: the simulator, the processing engine, and the interface.

### Simulator
Generates synthetic data of friendly and adversarial USVs operating in a 2D map with latitude and longitude coordinates.
- Friendly Units: Equipped with self-localization, velocity sensors, and adversarial detection.
- Adversarial Units: "Red team" units that move southward at constant velocity to test swarm response.
- Behavior: Friendly units target adversarial units and move to intercept them. 

### Backend
- Data Ingestion: Stream real-time data from friendly USVs and adversarial units.
- Processing Pipeline: Data processing and analysis for LLM retrieval.
- RAG Engine: Links user queries with retrieved log context to generate human-readable information and recommendations.

### Frontend UI
- Tactical Map: Interactive 2D visualization of the maritime space showing real-time activity.
- Command Console: A natural language prompt interface to easily interact with the RAG engine.