---
name: playwright
description: Browser automation and web scraping using Playwright MCP. Use when users ask to automate browser tasks, scrape web pages, take screenshots, fill forms, navigate websites, or interact with web elements programmatically.
---

# Playwright Skill

An expert agent for browser automation and web interactions using Playwright MCP.

## Capabilities

- **Browser Navigation**: Open URLs, navigate back/forward, handle redirects
- **Web Scraping**: Extract data from web pages (text, tables, images)
- **Screenshot Capture**: Full page, viewport, or element screenshots
- **Form Automation**: Fill inputs, select options, submit forms
- **Element Interaction**: Click, hover, drag, keyboard input
- **Wait Handling**: Wait for elements, network idle, custom conditions
- **Multi-Page Management**: Handle popups, iframes, new tabs

## Playwright MCP Tools

### Navigation Tools
- `playwright_navigate` - Navigate to URL
- `playwright_go_back` - Go back in history
- `playwright_go_forward` - Go forward in history
- `playwright_reload` - Reload current page

### Screenshot Tools
- `playwright_screenshot` - Take screenshot of page or element
- `playwright_get_clipboard_screenshot` - Get screenshot from clipboard

### Element Interaction
- `playwright_click` - Click element by selector
- `playwright_fill` - Fill input field
- `playwright_select` - Select dropdown option
- `playwright_hover` - Hover over element
- `playwright_drag_and_drop` - Drag and drop elements

### Content Extraction
- `playwright_get_page_info` - Get page title, URL, content
- `playwright_get_element` - Get element attributes/text
- `playwright_extract_content` - Extract structured data

### Form Handling
- `playwright_fill_form` - Fill multiple form fields
- `playwright_submit_form` - Submit a form
- `playwright_check` - Check/uncheck checkboxes
- `playwright_radio_select` - Select radio button

### Wait & Condition
- `playwright_wait_for_selector` - Wait for element
- `playwright_wait_for_timeout` - Wait for duration
- `playwright_wait_for_navigation` - Wait for navigation

## Workflow

### Step 1: Define Task

1. Identify the target URL
2. Determine required actions (navigate, scrape, interact)
3. Plan element selectors

### Step 2: Execute Actions

| Task Type | Tools to Use |
|-----------|-------------|
| Open page | `playwright_navigate` |
| Get data | `playwright_extract_content` |
| Screenshot | `playwright_screenshot` |
| Fill form | `playwright_fill`, `playwright_click` |
| Multi-page | Handle via `playwright_navigate` with new contexts |

### Step 3: Handle Results

1. Parse extracted content
2. Save to file or return to user
3. Clean up resources

## Common Selectors

```javascript
// CSS Selectors
await page.locator('button.submit').click()
await page.locator('#username').fill('user')

// XPath
await page.locator('//button[text()="Submit"]').click()

// Text Content
await page.get_by_text('Sign In').click()

// Placeholder
await page.get_by_placeholder('Email').fill('test@example.com')
```

## Example Operations

### Navigate and Screenshot
```javascript
await playwright_navigate({ url: "https://example.com" })
await playwright_screenshot({ fullPage: true, path: "screenshot.png" })
```

### Fill and Submit Form
```javascript
await playwright_fill({ selector: "#email", value: "user@example.com" })
await playwright_fill({ selector: "#password", value: "secret123" })
await playwright_click({ selector: "button[type='submit']" })
```

### Extract Table Data
```javascript
await playwright_extract_content({
  selector: "table.data",
  type: "table"
})
```

## Error Handling

- Use `playwright_wait_for_selector` with timeout to ensure elements exist
- Wrap actions in try-catch for graceful error handling
- Check for network errors and handle redirects

## Output Format

Provide:
1. Summary of browser actions performed
2. Extracted data (if applicable)
3. Screenshot paths (if taken)
4. Any errors encountered
