# Alerts Guide

## Alert Types

| Type | Triggers When |
|------|---------------|
| Price Threshold | Price crosses a specified level |
| Indicator Cross | Indicator crosses a threshold |
| Signal Trigger | A trading signal is generated |
| Volume Spike | Volume exceeds N× average |
| Trend Break | Trend line or MA is broken |
| Compound | Combination of multiple conditions |

## Managing Alerts

Alerts can be created, listed, dismissed, and deleted via the API or UI. Active alerts are evaluated in a background loop and dispatched via WebSocket.
