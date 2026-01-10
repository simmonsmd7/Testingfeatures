# Task: Grey Hat SaaS Opportunity Research

## Objective

Discover truly novel, underserved SaaS opportunities that exist in legal grey areas, regulatory gaps, or markets that mainstream players avoid due to complexity, stigma, or perceived risk. Focus on opportunities with few or no existing competitors.

## Research Focus Areas

### 1. Regulatory Arbitrage Opportunities
- Services legal in some jurisdictions but underserved due to complexity
- Compliance tools for industries with fragmented/unclear regulations
- Cross-border services exploiting regulatory differences

### 2. Stigmatized but Legal Markets
- Industries banks/payment processors avoid (legal cannabis, adult content creators, etc.)
- Services for controversial but legal professions
- Tools for grey market resellers, arbitrageurs, dropshippers

### 3. Automation of "Unsexy" Workflows
- Debt collection, skip tracing, asset recovery tools
- Reputation management/removal services
- Competitive intelligence/OSINT automation
- Price monitoring and dynamic repricing

### 4. Platform Policy Exploits
- Tools that work within TOS grey areas of major platforms
- Services helping banned/restricted accounts recover
- Multi-account management, identity separation tools

### 5. Data Brokerage & Intelligence
- People search/background check alternatives
- Business intelligence from public records
- Sentiment analysis and prediction markets

### 6. Financial Grey Zones
- Crypto payment rails for underbanked businesses
- Invoice factoring for rejected industries
- Alternative credit scoring for thin-file borrowers

## Research Methodology

Each iteration should:

1. **Pick ONE unexplored angle** from the focus areas above
2. **Search for existing solutions** - verify the gap actually exists
3. **Identify the pain point** - why do people need this?
4. **Assess legal risk** - is this actually legal? What jurisdictions?
5. **Estimate market size** - who would pay and how much?
6. **Document competitive landscape** - who else is doing this?
7. **Rate the opportunity** (1-10) based on:
   - Market gap (fewer competitors = higher score)
   - Legal clarity (clearer = higher score)
   - Monetization potential
   - Technical feasibility
   - Defensibility/moat potential

## Output Format

For each opportunity discovered, document in ralph.log:

```
=== OPPORTUNITY: [Name] ===
Category: [Which focus area]
Pain Point: [What problem does this solve]
Target Customer: [Who pays]
Existing Competition: [List competitors or "NONE FOUND"]
Legal Status: [Legal/Grey/Varies by jurisdiction]
Risk Factors: [What could go wrong]
Monetization: [How to charge, estimated pricing]
Technical Complexity: [Low/Medium/High]
Market Size Estimate: [TAM if possible]
SCORE: [X/10]
Sources: [URLs researched]
```

## Success Criteria

- [ ] Minimum 3 opportunities documented per iteration
- [ ] Each opportunity has verified competition research
- [ ] Legal status is assessed (not just assumed)
- [ ] At least one "NONE FOUND" competitor opportunity per session
- [ ] Sources cited for all claims

## Constraints

- Focus on B2B SaaS, not consumer apps
- Must be legal in at least US, EU, or major English-speaking market
- Avoid anything requiring regulatory licenses (banking, healthcare, legal)
- No opportunities requiring significant capital (keep bootstrappable)
- Prefer recurring revenue models over one-time

## Research Tools to Use

- Web search for competitor analysis
- Search "[industry] + software" "[problem] + SaaS" "[workflow] + automation"
- Check Product Hunt, G2, Capterra for existing solutions
- Search Reddit, Twitter, forums for complaints/pain points
- Check startup databases (Crunchbase patterns)

## Anti-Patterns to Avoid

- Don't suggest ideas that already have 10+ funded competitors
- Don't suggest anything requiring deep domain expertise to build
- Don't focus on "nice to have" - find "hair on fire" problems
- Don't suggest anything a solo dev couldn't MVP in 2-3 months

## When Complete

After documenting opportunities, output:
"ITERATION COMPLETE - [X] opportunities logged"

Then exit cleanly for next iteration.

---

## Progress Log Reference

Check `ralph.log` at start of each iteration to:
- See what's already been researched
- Avoid duplicate research
- Build on previous findings
- Identify patterns across iterations
