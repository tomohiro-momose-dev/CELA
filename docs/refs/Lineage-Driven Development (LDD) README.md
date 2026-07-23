# **🫧 Lineage-Driven Development (LDD)**

**"Development is the evolution of decisions."**

**"Git manages code lineage. LDD manages decision lineage."**

## **👁️ The Manifesto**

We are all drowning in chat bubbles.

In the era of AI-driven development (ADD), our daily workflow has become a repetitive, exhausting cycle: we open a chat session with an AI Agent, build a towering castle of context over dozens of turns, and then—inevitably—the AI hallucinates, loses its working memory, and the context collapses. We are forced to burn tokens, copy-paste requirements, and manually re-educate a fresh AI session from scratch.

This is because **LLMs are fundamentally stateless**. They do not remember. They mimic.

Current AI assistant practices treat conversations as ephemeral, disposable, and chaotic streams. We believe this is a paradigm error. Code is not the only asset we produce; the **decisions** that shaped the code are the true intellectual property of engineering.

**Lineage-Driven Development (LDD)** is a development methodology designed to govern, capture, and inherit the lineage of architectural decisions. It transforms temporary, volatile chat sessions into an immutable, structured historical record.

While **Git** tracks the lineage of your **code**, **LDD** tracks the lineage of your **decisions**.

# **The Problem**

Today's AI-assisted workflows suffer from several recurring failures:

* **Context Decay:** AI conversations become too long, dilute their own focus, and eventually collapse.  
* **Invisible Rationale:** Important structural decisions are buried inside thousands of chat messages, never to be seen again.  
* **The Cold Start Problem:** Every new chat session starts with zero memory, forcing developers to repeatedly explain the same rules.  
* **Lost Debates:** Team members cannot reconstruct *why* a certain decision was made, what alternatives were rejected, and what evidence led to the change.  
* **Ephemeral Knowledge:** AI-generated insights, debugging breakthroughs, and architectural guidelines disappear the moment a thread is closed.

In practice, developers repeatedly solve the same problems because previous reasoning cannot be efficiently inherited.

**Code survives. Decision history does not.**

# **Core Principle**

LDD treats AI conversations not as temporary chat logs, but as **first-class development artifacts**.

Instead of viewing a conversation as disposable context, LDD views it as a continuous, structured thread in the project’s knowledge graph. Every significant engineering activity must answer five fundamental questions:

1. **Trigger:** Why did this work begin? What was the symptom, error, or user instruction?  
2. **Decision (The Compass):** What conclusion was reached? What is the logical "why" behind the chosen path?  
3. **Evidence:** What cold, hard facts, experiments, console logs, or metrics support this decision?  
4. **Open Questions:** What remains unresolved or unverified?  
5. **Next Action:** What should happen next in the immediate implementation slice?

Together, these five elements form a highly compressed, reusable, and structured **Decision Lineage** that can be read by both humans and LLMs.

# **Hydrate**

**Hydrate** is the central operation of LDD.

A new AI conversation should never start from zero. Instead, it must inherit the relevant lineage of previous work.

Hydration is the process of reconstructing context from prior decision history and injecting it into a new thread.

The goal of Hydration is not to restore every single historical chat message. That is a waste of tokens and a vector for hallucination. Instead, the goal is to **restore the exact state of knowledge** necessary for a productive continuation. LDD intentionally prioritizes:

* Concrete Decisions  
* Logical Rationale (Rejected Alternatives)  
* Empirical Evidence  
* Open Backlog Work

over raw, noisy conversation history.

# **Context Is a Resource**

Traditional workflows assume context is unlimited. Modern LLM workflows prove otherwise: **context is a highly constrained, decaying resource** that must be managed deliberately.

By treating context as a physical resource with its own health and lifespan, LDD introduces structured operations to govern its lifecycle:

* **Context Refresh:** Cleanly terminating a decaying conversation and spawning a pristine thread.  
* **Context Hydration:** Re-injecting synthesized decision lineage into the newly spawned thread.  
* **Context Health:** Diagnosing when a thread's cognitive load is saturated and suggesting an optimal split point.  
* **Context Compression:** Condensing raw dialogue into high-density JSON/Markdown decision packages.  
* **Context Recovery:** Reconstructing past workspace realities (Git commits, pending tasks) in parallel sandboxes.

A healthy LDD workflow continuously and automatically transforms temporary conversations into durable knowledge assets.

# **Decision Lineage**

Source code has Git. AI-assisted development needs lineage.

Just as Git tracks file changes line-by-line, LDD builds a traceable, immutable chain of engineering intent. The lineage is a traceable chain of:

       Problem \[Trigger\]  
              │  
              ▼  
    Investigation \[Hypothesis\]  
              │  
              ▼  
       Decision \[The Compass\]  
              │  
              ▼  
   Implementation \[Changes\]  
              │  
              ▼  
       Evidence \[Verification\]  
              │  
              ▼  
     Future Work \[Next Action\]

By formalizing this chain, we ensure that every line of code in the repository can be traced back to the specific moment of human-AI synthesis that created it.

# **Reference Implementation: *Lineage***

While LDD is a methodology, **Lineage** is its physical manifest—a lightweight VS Code / Cursor extension designed to automate LDD operations:

* **Automated Lineage Harvesting:** Quietly hooks into the IDE's database to capture raw chat bubbles and automatically summarize them into LDD’s 5-Key Anchors using local SLMs.  
* **Context Hydration (Ctrl+Alt+R):** Instantly terminates a bloated thread, compiles a structured hydrateContext.md capsule, and launches a clean, fully hydrated session.  
* **Living ADR (Architecture Decision Records):** Automatically writes structured ADRs directly to docs/adr/ whenever a major decision node is finalized.  
* **Decision-to-Code Hover:** Hovering over any line of code in your editor reveals the exact conversation node, the trigger, and the rationale that generated it (coupling git blame with decision lineage).

## **📜 How to Practice LDD Today (Without the Extension)**

You can practice the core tenets of LDD manually in any editor with any AI today:

1. **Maintain a Single Source of Truth:** Keep a BACKLOG.md for task states and an AI\_plan.md for implementation plans. Never let the AI dictate what is "pending."  
2. **Execute Manual Refreshes:** Every 15-20 turns, close your chat. Write a 5-sentence summary of the **Trigger**, **Decision**, **Evidence**, and **Next Action**, and feed that summary into a new chat window.  
3. **Layer Your Requirements:** Avoid massive, monolithic documents. Split them into localized specifications (leaves) and refer the AI to them only on-demand.

## **📄 License & Contribution**

The LDD specification and its reference implementation, Lineage, are open-source. We believe that the future of AI-human collaboration lies in robust, local-first, zero-trust lineage management.

**"The code is just the final artifact. The journey, the decisions, and the rationale—the Lineage—is your true intellectual property."**

*Created by developers, for developers, governed by LDD v1.1.*