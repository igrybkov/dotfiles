---
name: explain
description: Explain code in the current context or a specific file
allowed-tools:
  - Read
  - Glob
  - Grep
---

# Code Explanation Skill

Explain code that the user is asking about. If no specific code is mentioned, explain the most recently discussed code or file.

## Workflow

1. **Start with the big picture**
   - What is the overall purpose of this code?
   - Where does it fit in the larger system?

2. **Break down the structure**
   - Key components, classes, or functions
   - How they relate to each other
   - Data flow through the code

3. **Explain non-obvious parts**
   - Complex algorithms or logic
   - Why certain design decisions were made (if apparent)
   - Edge cases being handled

4. **Highlight important details**
   - Side effects
   - Dependencies on external systems
   - Performance considerations
   - Security implications

## Output Format

- Use clear, concise language
- Include code snippets when referencing specific parts
- Use analogies if they help clarify complex concepts
- Adjust depth based on what the user is asking about

## Important Notes

- If you need to read additional files to understand the context better, do so
- Focus on explaining the "why" not just the "what"
