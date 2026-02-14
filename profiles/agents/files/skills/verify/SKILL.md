---
name: verify
description: Verify AI agent's work by double-checking all claims and outputs with evidence
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash(git*:*)
  - Bash(cat:*)
  - Bash(grep:*)
  - Bash(find:*)
  - Bash(ls:*)
  - Bash(wc:*)
  - Bash(head:*)
  - Bash(tail:*)
  - WebFetch
  - WebSearch
---

# Work Verification Skill

**Critical Requirement**: This skill forces the AI agent to rigorously verify every claim, statement, and output. No assumptions. No skipping. Everything must be double-checked with concrete evidence.

**Applies to**: Code, writing, analysis, research, documentation, data interpretation, summaries, reports, recommendations, and all other work products.

## Usage Modes

**Important**: When the user invokes this skill, check what they want verified:
- If they mention file paths → verify those files
- If they mention specific claims → verify those claims
- If they say just `/verify` → verify recent session work
- If unclear → ask them what they want verified

### Mode 1: Verify Recent Session Work
When invoked without arguments (`/verify`), verify all work produced in the current session.

**Example**: `/verify`

### Mode 2: Verify Specific Files
When the user provides file path(s), verify all claims in those specific files:
- `/verify path/to/report.md`
- `/verify analysis.txt data-summary.md`
- `/verify reports/*.md`
- User message: "Can you verify the Q4 report?" → Read the file and verify it

This mode is useful for:
- Fact-checking existing documents
- Verifying reports written outside this session
- Auditing analysis done by others
- Checking legacy documentation
- Reviewing work done by colleagues

### Mode 3: Verify Specific Claims
When the user provides specific claims to check:
- `/verify "User engagement increased 25%"`
- `/verify the statistics in section 3`
- User message: "Check if the revenue numbers are accurate" → Find and verify revenue numbers

## Verification Protocol

You MUST follow this protocol:

### 1. Identify All Claims

Go through everything you produced and list every factual claim or assertion you made. Include:

**For Code Work:**
- Statements about what code does
- Claims about file locations or contents
- Assertions about how systems work
- Descriptions of changes made
- Explanations of behavior
- Documentation of features

**For Analytical & Writing Work:**
- Statistical claims or data points
- Quotes or paraphrases from sources
- Numerical figures or calculations
- Date/time references
- Citations or attributions
- Causal relationships ("X causes Y")
- Comparisons ("A is larger than B")
- Historical facts or events
- Definitions or explanations
- Summary statements
- Conclusions drawn from data

### 2. Verify Each Claim

For **EVERY** claim identified above:

1. **State the claim** explicitly
2. **Determine verification method**: What evidence would prove or disprove this?
3. **Gather evidence**: Use tools to get concrete proof

   **For Code/Technical Work:**
   - Read actual files (don't rely on memory)
   - Run actual commands (don't assume output)
   - Check actual git history (don't guess)
   - Search actual code (don't presume)

   **For Analytical/Writing Work:**
   - Re-read source documents/files
   - Re-calculate numbers and statistics
   - Check original sources for quotes
   - Verify dates and times mentioned
   - Cross-reference claims across multiple sources
   - Search for contradicting information
   - Validate logical inferences
   - Check data sources and methodology

4. **Compare**: Does the evidence match the claim?
5. **Document result**:
   - ✅ VERIFIED: Evidence confirms claim
   - ❌ INCORRECT: Evidence contradicts claim
   - ⚠️ PARTIAL: Evidence partially supports claim
   - ❓ UNVERIFIABLE: Cannot gather evidence (state why)

### 3. Output Verification Table

At the end of your verification, provide a table with this format:

| # | Claim | Verification Method | Evidence | Result |
|---|-------|---------------------|----------|--------|
| 1 | "The function `foo()` is in `src/main.py`" | Read file and search for function | File read + grep for "def foo" at line 42 | ✅ VERIFIED |
| 2 | "The config uses port 8080" | Read config file | Found `port: 3000` in config.yml line 15 | ❌ INCORRECT |
| 3 | "User engagement increased 25%" | Re-read report + recalculate | Source shows 23% increase (from 1000 to 1230) | ❌ INCORRECT |
| 4 | "Document states 'high priority'" | Search source document | Exact quote found in section 2.3 | ✅ VERIFIED |
| 5 | "Total budget is $50,000" | Sum all line items | Actual total: $48,750 (calculation error) | ❌ INCORRECT |
| 6 | "Policy implemented Q3 2024" | Read meeting notes from Sept 2024 | Implementation date: July 15, 2024 (Q3) | ✅ VERIFIED |

### 4. Corrections

If any claims were incorrect or partially correct:

1. **Acknowledge the error**: Be explicit about what was wrong
2. **Provide correct information**: Based on actual evidence
3. **Explain the discrepancy**: If known, why was the original claim wrong?
4. **Update any affected work**: Fix documentation, code, or explanations

## Verification Examples

### Code Work Examples

#### Example 1: Code Change Verification

**Claim**: "I added error handling to the `process_data()` function"

**Verification**:
1. Read the file containing `process_data()`
2. Search for try/catch or error handling patterns
3. Compare with git diff to see what was actually added

#### Example 2: File Location Verification

**Claim**: "The configuration is stored in `config/settings.json`"

**Verification**:
1. Use Glob to find all config files
2. Read the file at the claimed path
3. Verify it contains configuration data

#### Example 3: Behavior Explanation Verification

**Claim**: "The system retries failed requests 3 times"

**Verification**:
1. Find the retry logic in code
2. Read the actual implementation
3. Check for the retry count constant or configuration

### Analytical & Writing Work Examples

#### Example 4: Statistical Claim Verification

**Claim**: "The report shows a 25% increase in user engagement"

**Verification**:
1. Re-read the source report/data file
2. Locate the actual engagement metrics
3. Recalculate the percentage change
4. Verify the baseline and comparison periods

#### Example 5: Quote Verification

**Claim**: "According to the document, 'performance improved significantly'"

**Verification**:
1. Read the source document
2. Search for the exact quote
3. Verify surrounding context
4. Check if paraphrasing is accurate

#### Example 6: Date/Historical Fact Verification

**Claim**: "The policy was implemented in Q3 2024"

**Verification**:
1. Read meeting notes or policy documents
2. Search for implementation dates
3. Verify against timeline documents
4. Cross-reference with related events

#### Example 7: Calculation Verification

**Claim**: "The total cost is $15,420 across 3 departments"

**Verification**:
1. Re-read the source data
2. Manually recalculate the sum
3. Verify all departments are included
4. Check for any rounding or currency conversions

#### Example 8: Summary Verification

**Claim**: "The main findings are X, Y, and Z"

**Verification**:
1. Re-read the entire source material
2. Identify all key findings mentioned
3. Verify no major findings were omitted
4. Check if X, Y, Z accurately reflect priorities

#### Example 9: Causal Relationship Verification

**Claim**: "The new feature caused user retention to increase"

**Verification**:
1. Read the analysis methodology
2. Check if other factors were controlled for
3. Verify timeline (correlation vs causation)
4. Look for conflicting evidence or alternative explanations

## Important Rules

1. **Never skip verification**: Every single claim must be verified
2. **Don't rely on memory**: Always read/check actual sources
3. **Document uncertainty**: If you can't verify, say so explicitly
4. **Be honest about errors**: If you were wrong, admit it clearly
5. **Verify verifications**: Double-check your verification methods are sound
6. **Update as you verify**: If you find errors, fix them immediately

## Common Verification Pitfalls

**General:**
- ❌ "I'm pretty sure this is correct" → ✅ Verify with evidence
- ❌ "This should be right" → ✅ Check the actual source
- ❌ "I recall that..." → ✅ Re-read the original material
- ❌ "Approximately..." (when exact figures exist) → ✅ Get exact numbers

**Code Work:**
- ❌ "The file is probably in X directory" → ✅ Use Glob/Grep to confirm
- ❌ "Based on common patterns..." → ✅ Check this specific codebase
- ❌ "I added X feature" → ✅ Read the actual diff to confirm
- ❌ "This should work" → ✅ Test or read actual implementation

**Analytical Work:**
- ❌ "The document says something like..." → ✅ Find and quote exact text
- ❌ "Around 50 people..." → ✅ Get the exact number from source
- ❌ "This probably correlates with..." → ✅ Check if data actually shows correlation
- ❌ "The main point is..." → ✅ Re-read to verify it's actually the main point
- ❌ "According to studies..." → ✅ Cite the specific study/source
- ❌ "The data shows..." → ✅ Verify what the data actually shows (not interpretation)

## When to Use This Skill

Use this skill:
- After making significant code changes
- After writing documentation or explanations
- After completing analytical work or research
- After writing reports, summaries, or recommendations
- After processing data or creating visualizations
- After making claims based on sources
- When the user asks you to verify your work
- Before marking tasks as complete
- When accuracy is critical
- Before presenting findings or conclusions
- After any work where facts, figures, or claims were stated

## Workflow

### For Session Work (Mode 1)
1. **Review your recent work** (messages, code changes, files written, analysis, reports)
2. **Extract all factual claims** (make a comprehensive list)
3. **Verify each claim systematically** (use tools, gather evidence)
4. **Create the verification table** (show all results transparently)
5. **Make corrections** (fix any errors found)
6. **Summarize findings** (how many verified, how many errors, what was fixed)

### For Specific Files (Mode 2)
1. **Read the specified file(s)** completely
2. **Extract all factual claims** from the content (comprehensive list)
3. **For each claim, gather evidence** from:
   - Other files referenced in the document
   - Source data mentioned
   - Original sources for quotes
   - Re-calculations for numbers
4. **Create the verification table** showing what was checked
5. **Report findings**: Which claims are accurate, which need correction
6. **Do NOT modify files** unless explicitly asked - just report findings

### For Specific Claims (Mode 3)
1. **Identify the specific claims** the user wants verified
2. **Locate these claims** in files or recent work
3. **Verify each claim** with concrete evidence
4. **Create focused verification table** for just those claims
5. **Report findings** with details

## Types of Work This Applies To

- **Code & Development**: Changes, features, bug fixes, architecture
- **Documentation**: Technical docs, user guides, README files
- **Analysis**: Data analysis, performance analysis, competitive analysis
- **Research**: Literature review, fact-checking, source verification
- **Writing**: Reports, articles, summaries, presentations
- **Data Processing**: Calculations, aggregations, transformations
- **Recommendations**: Decisions based on data or analysis
- **Communication**: Emails, messages with factual claims

## Practical Usage Examples

### Example: Verify an Existing Report

**User**: `/verify reports/Q4-analysis.md`

**Agent should**:
1. Read `reports/Q4-analysis.md` completely
2. Extract all claims (statistics, dates, conclusions)
3. Find source data files referenced
4. Re-calculate any numbers mentioned
5. Verify all quotes and attributions
6. Create verification table
7. Report: "Found 15 claims, 13 verified, 2 incorrect"

### Example: Verify Specific Statistics

**User**: `/verify the revenue numbers in financial-summary.txt`

**Agent should**:
1. Read `financial-summary.txt`
2. Extract all revenue-related numbers
3. Locate source data (spreadsheets, databases)
4. Recalculate each figure
5. Create verification table for revenue claims only
6. Report findings

### Example: Verify Multiple Documents

**User**: `/verify docs/*.md`

**Agent should**:
1. Read all markdown files in docs/
2. Extract claims from each file
3. Verify systematically (may take multiple tool calls)
4. Create comprehensive verification table
5. Report findings per file

### Example: Check Someone Else's Analysis

**User**: `/verify analysis/competitor-research.md` (written by colleague)

**Agent should**:
1. Read the file without assuming it's correct
2. Treat every statement as needing verification
3. Find original sources mentioned
4. Re-verify data and calculations
5. Report findings objectively
6. Do NOT modify the file unless asked
