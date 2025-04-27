# Setting Up Slack Socket Mode

This guide explains how to set up and use Slack's Socket Mode instead of webhooks.

## Overview

Socket Mode establishes a WebSocket connection with Slack instead of using HTTP endpoints, which is useful when:
- You're developing locally without public endpoints
- You're behind a firewall
- You want to avoid setting up tunneling services

## Step 1: Get Required Tokens

You need two types of tokens:

1. **Bot Token** (starts with `xoxb-`)
   - Already configured in your app
   - Used for API interactions

2. **App-Level Token** (starts with `xapp-`)
   - Required for Socket Mode
   - Has the `connections:write` scope

### Creating an App Token:

1. Go to your [Slack App configuration page](https://api.slack.com/apps)
2. Select your app
3. Navigate to "Basic Information"
4. Scroll to "App-Level Tokens" section
5. Click "Generate Token and Scopes"
6. Name your token (e.g., "socket_mode")
7. Add the `connections:write` scope
8. Click "Generate"
9. Copy the token (starts with `xapp-`)

## Step 2: Enable Socket Mode

1. Go to your [Slack App configuration page](https://api.slack.com/apps)
2. Select your app
3. Navigate to "Socket Mode"
4. Toggle "Enable Socket Mode" to On

## Step 3: Configure Environment Variables

Add your App Token to `.env`:

```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_TOKEN=xapp-your-app-token
```

## Step 4: Run the Application

```bash
python -m backend.main
```

The application will:
- Start the FastAPI server
- Launch Socket Mode in a background thread
- Handle Slack events through the WebSocket connection

## Verifying Setup

When the application starts, you should see:
- "Socket Mode started successfully" message
- Logging that confirms "Connected to Slack with Socket Mode!"

## How It Works

1. The Socket Mode client connects to Slack using your App Token
2. Slack sends events through this connection instead of HTTP webhooks
3. Your application processes these events just like webhook events

## Troubleshooting

- **Connection Issues**: Ensure both tokens are correctly set in your `.env` file
- **Authentication Errors**: Verify the tokens are for the correct workspace
- **Missing Events**: Check that event subscriptions are enabled in your Slack app

## Benefits Over HTTP Webhooks

- No need for public URLs
- No need for `ngrok` or similar services
- Works behind firewalls
- Reduced latency for event delivery 