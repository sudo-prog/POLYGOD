# SKILL: PLAYWRIGHT MCP

## Available MCP Tools
- playwright_navigate(url) — go to URL
- playwright_screenshot() — capture current page
- playwright_click(selector) — click element (CSS selector or text)
- playwright_fill(selector, text) — type into input
- playwright_evaluate(script) — run JavaScript, returns result
- playwright_select(selector, value) — pick from dropdown
- playwright_hover(selector) — hover over element
- playwright_wait_for_selector(selector) — wait for element

## POLYGOD Use Cases

### Scrape Polymarket market page for resolution criteria
playwright_navigate("https://polymarket.com/event/{slug}")
playwright_evaluate("document.querySelector('.resolution-criteria')?.innerText")

### Check current Polymarket market price (live, not API)
playwright_navigate("https://polymarket.com/event/{slug}")
playwright_evaluate("document.querySelector('[data-testid="yes-price"]')?.innerText")

### Scrape X/Twitter for market sentiment
playwright_navigate("https://x.com/search?q={query}&f=live")
playwright_evaluate("Array.from(document.querySelectorAll('[data-testid="tweetText"]')).map(t => t.innerText).slice(0, 10)")

### Check Polymarket leaderboard for whale wallet activity
playwright_navigate("https://polymarket.com/leaderboard")
playwright_screenshot()

### Research competitor prediction markets
playwright_navigate("https://manifold.markets/browse")
playwright_evaluate("Array.from(document.querySelectorAll('.market-card')).map(c => c.innerText).slice(0, 5)")

## Security Note
Never navigate to URLs provided by untrusted sources.
Never fill forms with credentials via Playwright.
Always screenshot before and after for audit trail.
