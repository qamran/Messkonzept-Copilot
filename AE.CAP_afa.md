# AI Capstone Project - AI Engineering

> Source: Turing College website, copied 2026-11-23; updated 2026-11-27 with the new evals criterion ("AI evaluations" is now required, weights changed). Earlier copies are in git history.

## Objective

- Combine all the AI engineering knowledge you gained in the course and apply it in a single project.
- Deepen your knowledge of frameworks, tools, and techniques such as OpenRouter, LangChain, and RAG.
- Gain hands-on experience with tools like Streamlit, ChromaDB, and vector databases.
- Practice creating a full-scale AI application.
- Prepare for roles in AI/ML or as technical startup founders.

## Example Cases

Use the examples below or develop your own business idea or project. Use your domain knowledge to shape the project. If you are unsure whether your idea meets the capstone requirements, discuss it with your JTL/STL.

**Need ideas?** The Capstone is a guide to choosing and completing a project. It covers how to find a problem others are overlooking, eight frameworks for pressure-testing an idea before you commit, how to budget your time across choosing, building, testing and polishing, and a 13-step sequence that takes you from a first idea to a shipped project.

Spend some time exploring what other students have built on the Turing College Showcase for inspiration.

### Case 1: Retrieval-Augmented Generation (RAG)-powered knowledge assistant

**Objective:** Build a knowledge assistant that retrieves relevant data from external sources to provide precise and contextualised answers.

**Key Tools:** LangChain, ChromaDB, OpenRouter, Streamlit.

**Steps:**

1. **Data Preparation:**
   - Choose a dataset (e.g. company FAQs, product manuals, or educational content).
   - Process and embed the data using tools like OpenAI embeddings or Hugging Face.
2. **Vector Database Integration:**
   - Set up a vector database (e.g. ChromaDB) to store and retrieve embeddings.
3. **LangChain RAG:**
   - Create a chain combining retrieval and generation to build the assistant.
4. **Interactive UI:**
   - Use Streamlit to develop a user interface.
5. **Testing and Optimisation:**
   - Test the assistant's responses for accuracy and efficiency.
6. **Security Assessment:**
   - Document security considerations, including data privacy, access control, and prompt injection.

**Outcome:** A working knowledge assistant with a demo showing retrieval and generation.

### Case 2: AI agent for task automation

**Objective:** Develop an AI agent capable of automating complex workflows such as data analysis, report generation, or customer support.

**Key Tools:** LangChain, Python/JavaScript, OpenRouter, external APIs.

**Steps:**

1. **Agent Design:**
   - Define the agent's purpose and capabilities (e.g. analysing sales data, generating summaries).
2. **Tool Integration:**
   - Equip the agent with tools such as API calls, database queries, or web scraping.
3. **Agent Execution:**
   - Implement features like long-term memory, code execution, or multi-step reasoning.
4. **Interactive Prototyping:**
   - Build a prototype using Streamlit or another interface for live interaction.
5. **Evaluation:**
   - Assess the agent's accuracy and responsiveness through user testing.
6. **Documentation:**
   - Provide a report detailing functionality and security considerations.

**Outcome:** An AI agent that automates tasks using an LLM.

### Case 3: Smart document search system

**Objective:** Build a tool for efficiently searching large sets of documents, such as legal contracts, research papers, or technical manuals.

**Key Tools:** LangChain, Vector Databases (e.g. ChromaDB, Pinecone), PDF/HTML loaders.

**Steps:**

1. **Document Ingestion:**
   - Load and preprocess documents into a vector database.
2. **Search and Retrieval:**
   - Implement a semantic search system using embeddings and vector similarity queries.
3. **Contextual Responses:**
   - Use an LLM to generate context-aware responses or summaries based on retrieved documents.
4. **User Interface:**
   - Develop an interface to upload documents and query the system.

**Outcome:** A search system for professionals to find and summarise information from large document collections.

### Case 4: Multimodal AI application

**Objective:** Develop an AI application combining text and image processing capabilities.

**Key Tools:** Nano Banana via OpenRouter, Whisper, LangChain.

**Steps:**

1. **Image and Text Analysis:**
   - Allow users to upload images and generate captions or extract metadata.
2. **Cross-Modal Search:**
   - Build a system to retrieve relevant images or text based on user queries.
3. **Generative Features:**
   - Enable users to generate images from descriptions or vice versa.
4. **Interactive Application:**
   - Develop a user interface integrating text and image functionalities.

**Outcome:** A multimodal AI application that combines text and image capabilities.

### Case 5: Agent harness for multi-step tasks

An agent harness is the software around an LLM that manages its tools, context, saved state, and execution. It lets an agent work through a task, check progress, and continue after an interruption.

**Objective:** Build a reusable harness and demonstrate it on one domain workflow, such as research, document processing, or coding. Keep the workflow narrow enough to test thoroughly.

**Key Tools:** Python, OpenRouter, SQLite or JSON files for saved state.

**Steps:**

1. **Define the workflow:**
   - Choose a task requiring several tool calls. Define its inputs, expected outputs, and checks for successful completion.
2. **Build the execution loop:**
   - Use a model with tool-calling support through OpenRouter. Send the task and available tools to the model, execute valid tool requests, and return results until the task finishes or a limit is reached.
3. **Save progress and resume:**
   - Save completed steps, tool results, and pending work at checkpoints. Restore the context needed to continue an interrupted run without repeating completed actions.
4. **Control execution:**
   - Restrict allowed tools and validate their arguments. Require user approval for consequential actions, such as sending messages or changing external records. Set maximum steps, time, cost, and retry counts.
5. **Record and evaluate runs:**
   - Record a trace of model requests, tool calls, results, and errors. Test a small task set, including failed tools and interrupted runs. Compare completion rate, cost, and recovery behaviour against a simple agent loop without checkpoints.

**Outcome:** A working harness demonstrated on your chosen workflow, with resumable execution, inspectable traces, and measured results explaining its strengths and limitations.

## Showcase your AI engineering knowledge

During the review, you are expected to answer questions across the following topics and explain your architecture decisions, trade-offs, and results:

- **Deployment:** Explain where your application runs, how you configure it and manage secrets, how you release updates, and how you handle failures.
- **AI evaluations:** Explain how you choose representative test tasks, define success criteria, and check that changes do not reduce quality on previously passing tasks. Show eval results for the core AI functionality of your project, and how you used them to improve it.
- **LLM observability:** Explain how you record and inspect model requests, tool calls, latency, token usage, and cost to diagnose problems.
- **AI safeguards:** Explain how you validate inputs and outputs, control access and tool permissions, protect sensitive data, and address prompt injection, where untrusted content tries to redirect the model.
- **Agentic workflows:** Explain how tools, saved state, retries, execution limits, and human oversight support tasks involving multiple steps.
- **Agentic coding techniques:** Explain how you use AGENTS.md instructions, planning, codebase exploration, reusable agent skills, and code review to guide coding agents. Show how you verify generated code and keep changes aligned with project requirements.

You don't need to implement every topic. Implement the ones relevant to your project, and be ready to explain the others. The exception is AI evaluations: your capstone must include them.

Implement the features relevant to your chosen project and bring evidence from working runs, such as evaluation results, logs, and failure tests. Be ready to explain which approaches you used, what you learnt, and their limitations. For topics that do not require implementation in your project, explain their relevance and why you chose that scope.

## Evaluation criteria

Your reviewer scores each criterion separately. The percentages below are rounded shares of the final score.

| Area | What the reviewer checks | Approx. weight |
|---|---|---|
| Application and functionality | Completeness and functionality of the project. | 20% |
| Application and functionality | User interface and interaction quality (if applicable). | 13% |
| Application and functionality | Clear explanation of purpose, implementation, and impact. A concise README.md paragraph explains the goal, the problem solved, and how the project works. | 7% |
| AI engineering techniques | Effective use and understanding of frameworks and tools (e.g. LangChain, Claude Code, OpenRouter). | 13% |
| AI engineering techniques | Best practices applied in AI engineering and application design. | 13% |
| AI engineering techniques | Effective use of evals for optimising and ensuring the reliability of core AI functionalities. See AI evaluations. | 13% |
| Security and quality | Awareness of security, privacy, and quality considerations in AI application development. | 13% |
| Showcase submission (optional) | Upload before the review and include the link in your README.md. See showcase details. | 7% |

## Capstone Showcase

Uploading your project to showcase.turingcollege.com is optional and counts for a small part of your final score. If you choose to upload it, do so before booking the review and include the link in your project's README.md.

Keep in mind:

- Your showcase entry must reflect the current state of your project. If you update the project, including after a resit, update the showcase entry.
- Include the link near the top of your README.md.

Project presentations are optional, though we recommend sharing yours with fellow students during a morning standup session. Presenting helps you consolidate what you've learned, get feedback from peers and leads, and practise explaining technical work. You can refer to the last part of The Capstone for guidance on presenting your project. Your STL and JTL will provide information on available presentation slots.

**Format:** 10 minutes to present, followed by 5 minutes for questions.

Structure your presentation around these six points:

1. **The problem** — What are you solving, who is it for, and why does it matter?
2. **Your solution** — What did you build? Walk through the architecture, models, and key tools.
3. **The data** — What data did you work with, and how did you prepare or handle it?
4. **Evaluation** — How did you measure success? Share your metrics and results.
5. **Challenges** — What was the hardest technical problem, and how did you solve it?
6. **What's next** — What would you improve or build with more time?

## Submission and scheduling a project review

To submit the capstone and allow the reviewer to view your work beforehand, you need to use the GitHub repository that has been created for you. Please go through the submission materials to learn more about submitting projects, scheduling project reviews, and using GitHub.
