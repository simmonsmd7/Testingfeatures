# Task: Grey Hat Software Opportunity Research

## Objective

Research novel grey hat software opportunities with little or no competition. These are tools that violate platform TOS but aren't illegal - where real money is being made by small teams.

## Proven Grey Hat Categories

### 1. Scraping & Data Resale
- Amazon product/pricing data APIs
- LinkedIn profile scraping for sales/recruiters
- Real estate listing aggregation
- Google Maps/Yelp business data extraction
- Job posting aggregators
- Court records / public filings databases
- Competitor pricing monitoring

### 2. E-commerce Exploits
- Sneaker/GPU/PS5 checkout bots
- Buy Box monitoring and sniping
- Inventory checkers (Walmart, Target, Best Buy)
- Review manipulation detection (sell to brands)
- MAP violation tracking
- Dropship supplier price monitors
- Amazon hijacker alerts

### 3. Social Media Automation
- Instagram/TikTok/Twitter growth bots
- Multi-account management dashboards
- Comment/DM automation tools
- Engagement pods as a service
- Follower/like marketplaces
- Content scheduling with auto-engagement
- Shadowban detection tools

### 4. SEO/Marketing Grey Area
- Private Blog Network (PBN) management
- Backlink building/selling platforms
- Competitor ad spy tools (Google/Meta/TikTok ads)
- Content spinning/AI rewriting at scale
- Rank tracking with SERP scraping
- Negative SEO detection (or services)
- Expired domain finders with metrics

### 5. Financial/Betting Arbitrage
- Sports betting arbitrage finders
- Prediction market bots (Polymarket, Kalshi)
- Crypto sniping/MEV bots
- SEC filing parsers (faster than official feeds)
- Options flow unusual activity alerts
- Credit card churning optimizers
- Bank bonus trackers

### 6. Account & Access Arbitrage
- Streaming account resale/generators
- .edu email providers (for student discounts)
- Phone verification services (SMS)
- Residential proxy networks
- Account unbanning services
- Multi-account identity management

### 7. Ticket & Reservation Bots
- Concert/event ticket sniping
- Restaurant reservation bots (Resy, OpenTable)
- Appointment grabbers (DMV, visa, passport, doctor)
- Limited drop monitors (sneakers, collectibles)
- Waitlist position holders

### 8. Gaming & Virtual Goods
- Game bot automation (farming, leveling)
- Virtual currency/item marketplaces
- Account selling platforms
- Cheat/hack subscriptions
- Private server hosting

## Research Mission

Find opportunities where:
1. **Gap exists** - no dominant player or existing tools suck
2. **People pay** - proven willingness (check Fiverr, Discord, Telegram for manual services)
3. **Defensible** - some technical moat or first-mover advantage
4. **Bootstrappable** - solo dev can MVP in 1-3 months

## Research Questions

For each opportunity:
1. **Who's paying today?** (find Discord servers, Telegram groups, Reddit threads)
2. **What do they pay?** (actual pricing from competitors or manual services)
3. **Who are competitors?** (find them, assess weaknesses)
4. **What's the gap?** (why would someone switch to you?)
5. **Technical difficulty?** (anti-bot measures, infrastructure needs)
6. **Legal/TOS risk?** (cease & desist likelihood, account bans)
7. **Moat?** (data accumulation, network effects, switching costs)

## Scoring (1-10 each, max 70)

- **Market Gap**: Less competition = higher
- **Proven Demand**: People already paying = higher
- **Willingness to Pay**: Higher prices = higher
- **Technical Feasibility**: Easier to build = higher
- **Legal Clarity**: Lower risk = higher
- **Scalability**: Grows without linear cost = higher
- **Defensibility**: Harder to copy = higher

## Output Format

Log to ralph.log:

```
=== OPPORTUNITY: [Name] ===
Category: [From list above]
Customer: [Specific persona - "Amazon FBA sellers doing $50k+/mo"]
Pain Point: [Exact problem]
Current Solutions: [Competitors + their weaknesses]
Gap: [Your angle]
Evidence of Demand: [Discord servers, Reddit complaints, Fiverr gigs]
Pricing: [What market bears - "$97/mo" or "$0.01/query"]
Technical Complexity: [Low/Medium/High + specifics]
Legal Risk: [Low/Medium/High + what could happen]
Moat: [Why hard to copy]

SCORES:
- Market Gap: X/10
- Proven Demand: X/10
- Willingness to Pay: X/10
- Technical Feasibility: X/10
- Legal Clarity: X/10
- Scalability: X/10
- Defensibility: X/10
TOTAL: XX/70

Notes: [Any other observations]
---
```

## Research Tactics

- Search Reddit: r/Entrepreneur, r/SaaS, r/juststart, r/dropship, r/FulfillmentByAmazon, r/wallstreetbets, r/churning
- Find Discord/Telegram groups where people discuss tools
- Check what people sell on Fiverr/Upwork (manual = automation opportunity)
- Search "[tool] alternative" or "[tool] sucks"
- Look at AppSumo lifetime deals (signals bootstrapper markets)
- Check Twitter/X for complaints about existing tools
- Browse BlackHatWorld, MP Social forums

## Anti-Patterns

- Skip if 5+ well-funded competitors exist
- Skip if requires enterprise sales
- Skip if needs real-time millisecond infrastructure
- Skip if clearly criminal (fraud, identity theft, hacking)
- Skip if you'd need a team of 10 to build MVP

## Success Criteria

- [ ] 3+ opportunities documented per iteration
- [ ] At least one scores 50+/70
- [ ] Found actual evidence of demand (links to communities/complaints)
- [ ] Identified specific gap vs existing solutions
- [ ] Realistic about legal risk

## When Complete

Output: "ITERATION COMPLETE - [X] opportunities logged, top score: [XX]/70"

Exit for next iteration.

---

## Progress Log

Check ralph.log before starting to avoid duplicate research.
