# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |
| < 1.0   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email the maintainer at `dipropaul032@gmail.com` with a description of the vulnerability
3. Include steps to reproduce the issue if possible
4. You will receive a response within 72 hours

## Scope

This package is designed for legitimate scraping of publicly available YouTube video data. The following are **out of scope** and will not be fixed or supported:

- Bypassing CAPTCHAs or bot detection
- Circumventing YouTube authentication
- Harvesting credentials or personal data
- Scraping private or age-restricted content without authorization

If you find that the package can be used to bypass YouTube's access controls, please report it so it can be addressed.

## Security Considerations

- The package uses a real browser (Selenium/Chrome) and does not inject custom JavaScript
- The package does **not** attempt to bypass CAPTCHAs — it detects and reports access challenges
- The innertube API key used by the package is publicly embedded in every YouTube watch page and is not a private credential
- The Return YouTube Dislike API is a public third-party service
- No credentials, cookies, or authentication tokens are stored or transmitted
